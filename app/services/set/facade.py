"""SetService facade — composes all set sub-services into a single drop-in replacement."""

from __future__ import annotations

from typing import Any

from app.core.errors import ValidationError
from app.core.pagination import CursorPage
from app.core.schemas import SetSummary
from app.models.set import DjSet, SetConstraint, SetFeedback, SetItem, SetVersion
from app.repositories.feature import FeatureRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository
from app.services.set.builder import SetBuilderService
from app.services.set.cheatsheet import SetCheatSheetService
from app.services.set.crud import SetCrudService
from app.services.set.scoring import SetScoringService


class SetService:
    """Facade that composes SetCrudService, SetBuilderService, SetScoringService,
    and SetCheatSheetService. Drop-in replacement for the original SetService.
    """

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

        self._crud = SetCrudService(set_repo, track_repo)
        self._builder = SetBuilderService(set_repo, playlist_repo, feature_repo)
        self._scoring = SetScoringService(set_repo, feature_repo, transition_repo)
        self._cheatsheet = SetCheatSheetService(set_repo, track_repo, feature_repo)

    # ── Read — delegated to _crud ─────────────────────

    async def get_by_id(self, set_id: int) -> DjSet:
        return await self._crud.get_by_id(set_id)

    async def get_by_query(self, query: str) -> DjSet:
        return await self._crud.get_by_query(query)

    async def list_all(
        self,
        *,
        template: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> CursorPage[DjSet]:
        return await self._crud.list_all(template=template, limit=limit, cursor=cursor)

    async def get_latest_version(self, set_id: int) -> SetVersion | None:
        return await self._crud.get_latest_version(set_id)

    async def get_version_items(self, version_id: int) -> list[SetItem]:
        return await self._crud.get_version_items(version_id)

    async def get_version_by_label(self, set_id: int, label: str) -> SetVersion | None:
        return await self._crud.get_version_by_label(set_id, label)

    async def get_two_latest_versions(self, set_id: int) -> list[SetVersion]:
        return await self._crud.get_two_latest_versions(set_id)

    async def get_version_by_id(self, version_id: int) -> SetVersion | None:
        return await self._crud.get_version_by_id(version_id)

    async def get_version_track_ids(self, version_id: int) -> list[int]:
        return await self._crud.get_version_track_ids(version_id)

    # ── Write — delegated to _crud ────────────────────

    async def create(
        self,
        name: str,
        description: str | None = None,
        target_duration_ms: int | None = None,
        template: str | None = None,
    ) -> DjSet:
        return await self._crud.create(
            name=name,
            description=description,
            target_duration_ms=target_duration_ms,
            template=template,
        )

    async def update(self, set_id: int, **fields: Any) -> DjSet:
        return await self._crud.update(set_id, **fields)

    async def delete(self, set_id: int) -> bool:
        return await self._crud.delete(set_id)

    async def add_constraint(
        self,
        set_id: int,
        constraint_type: str,
        constraint_value: Any,
    ) -> SetConstraint:
        return await self._crud.add_constraint(set_id, constraint_type, constraint_value)

    async def remove_constraint(self, constraint_id: int) -> bool:
        return await self._crud.remove_constraint(constraint_id)

    async def add_feedback(
        self,
        version_id: int,
        rating: int,
        feedback_type: str = "general",
        notes: str | None = None,
        set_item_id: int | None = None,
    ) -> SetFeedback:
        return await self._crud.add_feedback(
            version_id=version_id,
            rating=rating,
            feedback_type=feedback_type,
            notes=notes,
            set_item_id=set_item_id,
        )

    # ── Build / Rebuild — delegated to _builder ───────

    async def build_set(
        self,
        playlist_id: int,
        name: str,
        template: str | None = None,
        target_duration_min: int | None = None,
        algorithm: str = "greedy",
    ) -> tuple[DjSet, SetVersion, float | None, str]:
        return await self._builder.build_set(
            playlist_id=playlist_id,
            name=name,
            template=template,
            target_duration_min=target_duration_min,
            algorithm=algorithm,
        )

    async def build_set_dry_run(
        self,
        playlist_id: int,
        template: str | None = None,
        algorithm: str = "greedy",
    ) -> dict[str, Any]:
        return await self._builder.build_set_dry_run(
            playlist_id=playlist_id,
            template=template,
            algorithm=algorithm,
        )

    async def rebuild_set(
        self,
        set_id: int,
        pin_tracks: list[int] | None = None,
        exclude_tracks: list[int] | None = None,
        version_label: str | None = None,
        algorithm: str = "greedy",
    ) -> SetVersion:
        return await self._builder.rebuild_set(
            set_id=set_id,
            pin_tracks=pin_tracks,
            exclude_tracks=exclude_tracks,
            version_label=version_label,
            algorithm=algorithm,
        )

    # ── Scoring — delegated to _scoring ───────────────

    async def score_pair(self, from_id: int, to_id: int) -> dict[str, Any]:
        return await self._scoring.score_pair(from_id, to_id)

    async def get_transition_candidates(self, track_id: int, top_n: int = 10) -> dict[str, Any]:
        return await self._scoring.get_transition_candidates(track_id, top_n)

    async def score_set_transitions(self, set_id: int) -> dict[str, Any]:
        return await self._scoring.score_set_transitions(set_id)

    # ── Cheat sheet — delegated to _cheatsheet ────────

    async def get_cheat_sheet(self, set_id: int, version: str | None = None) -> str:
        return await self._cheatsheet.get_cheat_sheet(set_id, version)

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
                    track_count=len(latest.items) if latest and latest.items else 0,
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

        result = await self._sets.load_version_with_items(dj_set.id)
        latest = result[0] if result else None
        response = self.to_summary_sync(dj_set, latest).model_dump()

        if view in ("tracks", "full") and result:
            _, items = result
            track_ids = [item.track_id for item in items]
            artist_map = await self._tracks.get_artist_names_batch(track_ids)
            tracks_map = await self._tracks.get_by_ids(track_ids)
            tracks = []
            for item in items:
                t = tracks_map.get(item.track_id)
                if t:
                    tracks.append(
                        {
                            "position": item.sort_index,
                            "pinned": item.pinned,
                            "id": t.id,
                            "title": t.title,
                            "artist_names": artist_map.get(t.id, []),
                            "duration_ms": t.duration_ms,
                        }
                    )
            response["tracks"] = tracks

        if view in ("transitions", "full") and latest:
            response["version_id"] = latest.id
            response["version_label"] = latest.label
            response["quality_score"] = latest.quality_score

            items = result[1] if result else []
            transitions: list[dict[str, Any]] = []
            for i in range(len(items) - 1):
                from_id = items[i].track_id
                to_id = items[i + 1].track_id
                existing = await self._transitions.get_score(from_id, to_id)
                if existing is None:
                    transitions.append(
                        {
                            "position": i,
                            "from_track_id": from_id,
                            "to_track_id": to_id,
                            "scored": False,
                        }
                    )
                    continue
                transitions.append(
                    {
                        "position": i,
                        "from_track_id": from_id,
                        "to_track_id": to_id,
                        "overall_quality": existing.overall_quality,
                        "bpm_score": existing.bpm_score,
                        "harmonic_score": existing.harmonic_score,
                        "energy_score": existing.energy_score,
                        "spectral_score": existing.spectral_score,
                        "groove_score": existing.groove_score,
                        "timbral_score": existing.timbral_score,
                        "hard_reject": bool(existing.hard_reject),
                        "reject_reason": existing.reject_reason,
                        "scored": True,
                    }
                )
            response["transitions"] = transitions

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
