"""Set service — business logic for DJ set CRUD, building, and versioning.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

import json as _json
from typing import Any

from app.core.errors import NotFoundError, ValidationError
from app.core.pagination import CursorPage
from app.core.schemas import SetSummary
from app.models.set import DjSet, SetConstraint, SetFeedback, SetItem, SetVersion
from app.repositories.feature import FeatureRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository
from app.services.transition import TrackFeatures, TransitionScorer


class SetService:
    """Business logic for DJ sets: CRUD, build, rebuild, score transitions."""

    def __init__(
        self,
        set_repo: SetRepository,
        track_repo: TrackRepository,
        playlist_repo: PlaylistRepository,
        feature_repo: FeatureRepository,
        transition_repo: TransitionRepository,
    ) -> None:
        self._sets = set_repo
        self._tracks = track_repo
        self._playlists = playlist_repo
        self._features = feature_repo
        self._transitions = transition_repo

    # ── Read ─────────────────────────────────────────

    async def get_by_id(self, set_id: int) -> DjSet:
        dj_set = await self._sets.get_by_id(set_id)
        if dj_set is None:
            raise NotFoundError("Set", set_id)
        return dj_set

    async def get_by_query(self, query: str) -> DjSet:
        """Find set by name search."""
        dj_set = await self._sets.search_by_name(query)
        if dj_set is None:
            raise NotFoundError("Set", query)
        return dj_set

    async def list_all(
        self,
        *,
        template: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> CursorPage[DjSet]:
        return await self._sets.list_filtered(template=template, limit=limit, cursor=cursor)

    async def get_latest_version(self, set_id: int) -> SetVersion | None:
        return await self._sets.get_latest_version(set_id)

    async def get_version_items(self, version_id: int) -> list[SetItem]:
        return await self._sets.get_version_items(version_id)

    async def get_version_by_label(self, set_id: int, label: str) -> SetVersion | None:
        return await self._sets.get_version_by_label(set_id, label)

    async def get_two_latest_versions(self, set_id: int) -> list[SetVersion]:
        return await self._sets.get_latest_versions(set_id, count=2)

    async def get_version_by_id(self, version_id: int) -> SetVersion | None:
        return await self._sets.get_version_with_items(version_id)

    async def get_version_track_ids(self, version_id: int) -> list[int]:
        items = await self._sets.get_version_items(version_id)
        return [item.track_id for item in items]

    # ── Write ────────────────────────────────────────

    async def create(
        self,
        name: str,
        description: str | None = None,
        target_duration_ms: int | None = None,
        template: str | None = None,
    ) -> DjSet:
        if not name:
            raise ValidationError("name is required")
        dj_set = DjSet(
            name=name,
            description=description,
            target_duration_ms=target_duration_ms,
            template_name=template,
        )
        return await self._sets.create(dj_set)

    async def update(self, set_id: int, **fields: Any) -> DjSet:
        dj_set = await self.get_by_id(set_id)
        for key, value in fields.items():
            if hasattr(dj_set, key):
                setattr(dj_set, key, value)
        return await self._sets.update(dj_set)

    async def delete(self, set_id: int) -> bool:
        return await self._sets.delete(set_id)

    async def add_constraint(
        self,
        set_id: int,
        constraint_type: str,
        constraint_value: Any,
    ) -> SetConstraint:
        await self.get_by_id(set_id)  # verify exists
        value = (
            _json.dumps(constraint_value)
            if isinstance(constraint_value, dict | list)
            else constraint_value
        )
        constraint = SetConstraint(
            set_id=set_id,
            constraint_type=constraint_type,
            constraint_value=value,
        )
        return await self._sets.add_constraint(constraint)

    async def remove_constraint(self, constraint_id: int) -> bool:
        return await self._sets.remove_constraint(constraint_id)

    async def add_feedback(
        self,
        version_id: int,
        rating: int,
        feedback_type: str = "general",
        notes: str | None = None,
        set_item_id: int | None = None,
    ) -> SetFeedback:
        feedback = SetFeedback(
            version_id=version_id,
            rating=rating,
            feedback_type=feedback_type,
            notes=notes,
            set_item_id=set_item_id,
        )
        return await self._sets.add_feedback(feedback)

    # ── Build / Rebuild ──────────────────────────────

    async def build_set(
        self,
        playlist_id: int,
        name: str,
        template: str | None = None,
        target_duration_min: int | None = None,
        algorithm: str = "greedy",
    ) -> tuple[DjSet, SetVersion, float | None, str]:
        """Build optimized set from playlist.

        Returns (dj_set, version, quality_score, algorithm_used).
        """
        track_ids = await self._playlists.get_track_ids(playlist_id)
        if not track_ids:
            raise ValidationError("Playlist is empty")

        features_map = await self._features.get_scoring_features_batch(track_ids)
        track_features_list = [features_map.get(tid, TrackFeatures()) for tid in track_ids]

        optimized_order, quality, used_algorithm = self._optimize_order(
            track_ids,
            track_features_list,
            algorithm,
        )

        dj_set = DjSet(
            name=name,
            target_duration_ms=(target_duration_min * 60_000) if target_duration_min else None,
            template_name=template,
            source_playlist_id=playlist_id,
        )
        dj_set = await self._sets.create(dj_set)

        from app.utils.time import utc_timestamp_iso

        gen_meta = _json.dumps(
            {
                "algorithm": used_algorithm,
                "playlist_id": playlist_id,
                "track_count": len(optimized_order),
                "template": template,
                "target_duration_min": target_duration_min,
                "timestamp": utc_timestamp_iso(),
            }
        )
        version = await self._sets.create_version_with_meta(
            dj_set.id,
            optimized_order,
            label="v1",
            gen_meta=gen_meta,
        )

        return dj_set, version, quality, used_algorithm

    async def build_set_dry_run(
        self,
        playlist_id: int,
        template: str | None = None,
        algorithm: str = "greedy",
    ) -> dict[str, Any]:
        """Dry-run build — return stats without persisting."""
        track_ids = await self._playlists.get_track_ids(playlist_id)
        if not track_ids:
            raise ValidationError("Playlist is empty")

        features_map = await self._features.get_scoring_features_batch(track_ids)
        track_features_list = [features_map.get(tid, TrackFeatures()) for tid in track_ids]

        optimized_order, quality, used_algorithm = self._optimize_order(
            track_ids,
            track_features_list,
            algorithm,
        )

        return {
            "dry_run": True,
            "track_count": len(optimized_order),
            "algorithm": used_algorithm,
            "quality_score": round(quality, 4) if quality else None,
            "has_features": quality is not None,
            "template": template,
        }

    async def rebuild_set(
        self,
        set_id: int,
        pin_tracks: list[int] | None = None,
        exclude_tracks: list[int] | None = None,
        version_label: str | None = None,
    ) -> SetVersion:
        """Rebuild existing set with pin/exclude. Creates new version."""
        await self.get_by_id(set_id)  # validate set exists
        latest = await self._sets.get_latest_version(set_id)
        if latest is None:
            raise NotFoundError("SetVersion", f"set_id={set_id}")

        current_ids = await self.get_version_track_ids(latest.id)

        exclude_set = set(exclude_tracks or [])
        filtered = [tid for tid in current_ids if tid not in exclude_set]

        label = version_label or f"v{latest.id + 1}"

        items = [
            {
                "track_id": tid,
                "sort_index": idx,
                "pinned": tid in (pin_tracks or []),
            }
            for idx, tid in enumerate(filtered)
        ]
        version = await self._sets.create_version_with_items(set_id, items, label=label)

        return version

    # ── Scoring ──────────────────────────────────────

    async def score_pair(self, from_id: int, to_id: int) -> dict[str, Any]:
        """Score transition between two tracks. Save to DB."""
        existing = await self._transitions.get_score(from_id, to_id)
        if existing and existing.overall_quality is not None:
            return {
                "from_track_id": from_id,
                "to_track_id": to_id,
                "overall_quality": existing.overall_quality,
                "bpm_score": existing.bpm_score,
                "harmonic_score": existing.harmonic_score,
                "energy_score": existing.energy_score,
                "spectral_score": existing.spectral_score,
                "groove_score": existing.groove_score,
                "cached": True,
            }

        ft_from = await self._features.get_scoring_features(from_id)
        ft_to = await self._features.get_scoring_features(to_id)

        if not ft_from or not ft_to:
            return {
                "from_track_id": from_id,
                "to_track_id": to_id,
                "overall_quality": None,
                "message": "Missing audio features for one or both tracks",
            }

        scorer = TransitionScorer()
        score = scorer.score(ft_from, ft_to)

        from app.models.transition import Transition

        transition = Transition(
            from_track_id=from_id,
            to_track_id=to_id,
            overall_quality=score.overall if not score.hard_reject else 0.0,
            bpm_score=score.bpm,
            harmonic_score=score.harmonic,
            energy_score=score.energy,
            spectral_score=score.spectral,
            groove_score=score.groove,
        )
        await self._transitions.save_score(transition)

        return {
            "from_track_id": from_id,
            "to_track_id": to_id,
            "overall_quality": round(score.overall, 4) if not score.hard_reject else 0.0,
            "bpm_score": round(score.bpm, 4),
            "harmonic_score": round(score.harmonic, 4),
            "energy_score": round(score.energy, 4),
            "spectral_score": round(score.spectral, 4),
            "groove_score": round(score.groove, 4),
            "hard_reject": score.hard_reject,
            "reject_reason": score.reject_reason,
            "cached": False,
        }

    async def score_set_transitions(self, set_id: int) -> dict[str, Any]:
        """Score all sequential transitions in a set."""
        latest = await self._sets.get_latest_version(set_id)
        if not latest:
            raise NotFoundError("SetVersion", f"set_id={set_id}")

        items = await self._sets.get_version_items(latest.id)

        transitions_data = []
        for i in range(len(items) - 1):
            score_data = await self.score_pair(items[i].track_id, items[i + 1].track_id)
            score_data["position"] = i
            transitions_data.append(score_data)

        scored = [t for t in transitions_data if t.get("overall_quality") is not None]
        hard_conflicts = [t for t in scored if t.get("overall_quality") == 0.0]

        return {
            "set_id": set_id,
            "version_id": latest.id,
            "total_transitions": len(transitions_data),
            "scored_transitions": len(scored),
            "hard_conflicts": len(hard_conflicts),
            "avg_score": (
                sum(t["overall_quality"] for t in scored if t["overall_quality"])
                / max(1, len(scored) - len(hard_conflicts))
                if scored
                else None
            ),
            "transitions": transitions_data,
        }

    async def get_cheat_sheet(self, set_id: int) -> str:
        """Generate human-readable cheat sheet."""
        dj_set = await self.get_by_id(set_id)
        latest = await self._sets.get_latest_version(set_id)
        if not latest:
            raise NotFoundError("SetVersion", f"set_id={set_id}")

        items = await self._sets.get_version_items(latest.id)

        lines = [
            f"=== {dj_set.name} ===",
            f"Version: {latest.label or latest.id}",
            f"Tracks: {len(items)}",
            f"Score: {latest.quality_score or 'N/A'}",
            "",
        ]

        for i, item in enumerate(items, 1):
            track = await self._tracks.get_by_id(item.track_id)
            if track:
                line = f"{i:2d}. {track.title}"
                if item.pinned:
                    line += " [PINNED]"
                lines.append(line)

        return "\n".join(lines)

    # ── Tool-facing facades ─────────────────────────

    async def list_sets(
        self,
        *,
        template: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """List sets, returning a paginated response dict."""
        page = await self.list_all(template=template, limit=limit, cursor=cursor)
        items = []
        for s in page.items:
            latest = await self._sets.get_latest_version(s.id)
            items.append(
                SetSummary(
                    id=s.id,
                    name=s.name,
                    track_count=0,
                    template=s.template_name,
                    latest_score=latest.quality_score if latest else None,
                ).model_dump()
            )
        from app.core.schemas import PaginatedResponse

        return PaginatedResponse[SetSummary](
            items=items, next_cursor=page.next_cursor, total=page.total
        ).model_dump()

    async def get_set(
        self,
        *,
        id: int | None = None,
        query: str | None = None,
        view: str = "summary",
    ) -> dict[str, Any]:
        """Get set with variable detail level."""
        if id is not None:
            dj_set = await self.get_by_id(id)
        elif query is not None:
            dj_set = await self.get_by_query(query)
        else:
            raise ValidationError("Provide id or query")

        latest = await self._sets.get_latest_version(dj_set.id)
        response = self.to_summary_sync(dj_set, latest).model_dump()

        if view in ("tracks", "full") and latest:
            items = await self._sets.get_version_items(latest.id)
            tracks = []
            for item in items:
                t = await self._tracks.get_by_id(item.track_id)
                if t:
                    tracks.append(
                        {
                            "position": item.sort_index,
                            "pinned": item.pinned,
                            "id": t.id,
                            "title": t.title,
                            "duration_ms": t.duration_ms,
                        }
                    )
            response["tracks"] = tracks

        if view in ("transitions", "full") and latest:
            response["version_id"] = latest.id
            response["version_label"] = latest.label
            response["quality_score"] = latest.quality_score

        return response

    async def manage_set(self, *, action: str, data: dict[str, Any] | None) -> dict[str, Any]:
        """Dispatch set management actions."""
        valid = (
            "create",
            "update",
            "delete",
            "add_constraint",
            "remove_constraint",
            "add_feedback",
        )
        if action not in valid:
            raise ValidationError(f"Unknown action: {action}. Valid: {', '.join(valid)}")

        if action == "create":
            if not data or "name" not in data:
                raise ValidationError("data.name required for create")
            dj_set = await self.create(
                name=data["name"],
                description=data.get("description"),
                target_duration_ms=data.get("target_duration_ms"),
                template=data.get("template"),
            )
            return self.to_summary_sync(dj_set).model_dump()

        if action == "add_feedback":
            if not data or "version_id" not in data or "rating" not in data:
                raise ValidationError("data.version_id and data.rating required")
            fb = await self.add_feedback(
                version_id=data["version_id"],
                rating=data["rating"],
                feedback_type=data.get("feedback_type", "general"),
                notes=data.get("notes"),
                set_item_id=data.get("set_item_id"),
            )
            return {"feedback_id": fb.id, "version_id": data["version_id"]}

        set_id = (data or {}).get("id")
        if set_id is None:
            raise ValidationError("data.id required")

        if action == "delete":
            deleted = await self.delete(set_id)
            return {"deleted": deleted, "id": set_id}

        dj_set = await self.get_by_id(set_id)

        if action == "update":
            fields = {k: v for k, v in (data or {}).items() if k != "id"}
            if "template" in fields:
                fields["template_name"] = fields.pop("template")
            dj_set = await self.update(set_id, **fields)
            return self.to_summary_sync(dj_set).model_dump()

        if action == "add_constraint":
            if not data or "constraint_type" not in data or "constraint_value" not in data:
                raise ValidationError("data.constraint_type and data.constraint_value required")
            constraint = await self.add_constraint(
                set_id=set_id,
                constraint_type=data["constraint_type"],
                constraint_value=data["constraint_value"],
            )
            return {"constraint_id": constraint.id, "set_id": set_id}

        if action == "remove_constraint":
            constraint_id = (data or {}).get("constraint_id")
            if constraint_id is None:
                raise ValidationError("data.constraint_id required")
            removed = await self.remove_constraint(constraint_id)
            return {"removed": removed, "constraint_id": constraint_id}

        raise ValidationError("Unreachable")

    # ── Converters ───────────────────────────────────

    async def to_summary(self, dj_set: DjSet) -> SetSummary:
        latest = await self._sets.get_latest_version(dj_set.id)
        return SetSummary(
            id=dj_set.id,
            name=dj_set.name,
            track_count=len(latest.items) if latest and latest.items else 0,
            template=dj_set.template_name,
            latest_score=latest.quality_score if latest else None,
        )

    @staticmethod
    def to_summary_sync(dj_set: DjSet, version: SetVersion | None = None) -> SetSummary:
        return SetSummary(
            id=dj_set.id,
            name=dj_set.name,
            track_count=len(version.items) if version and version.items else 0,
            template=dj_set.template_name,
            latest_score=version.quality_score if version else None,
        )

    # ── Private ──────────────────────────────────────

    @staticmethod
    def _optimize_order(
        track_ids: list[int],
        track_features_list: list[TrackFeatures],
        algorithm: str,
    ) -> tuple[list[int], float | None, str]:
        """Run optimizer and return (ordered_ids, quality_score, algorithm_used)."""
        from app.services.optimizer import GeneticAlgorithm, GreedyChainBuilder

        scorer = TransitionScorer()
        has_features = any(f.bpm is not None for f in track_features_list)

        if not has_features:
            return track_ids, None, "playlist_order"

        if algorithm in ("ga", "genetic"):
            ga = GeneticAlgorithm(scorer)
            opt_result = ga.optimize(track_features_list, track_ids)
        else:
            builder = GreedyChainBuilder(scorer)
            opt_result = builder.build(track_features_list, track_ids)

        return opt_result.track_order, opt_result.quality_score, algorithm
