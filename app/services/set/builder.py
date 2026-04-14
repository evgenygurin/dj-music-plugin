"""Set builder sub-service — build and rebuild DJ sets."""

from __future__ import annotations

import json as _json
from typing import Any

from app.core.errors import NotFoundError, ValidationError
from app.db.models.set import DjSet, SetVersion
from app.db.repositories.feature import FeatureRepository
from app.db.repositories.playlist import PlaylistRepository
from app.db.repositories.set import SetRepository
from app.entities.audio.features import TrackFeatures
from app.templates.registry import get_template
from app.transition.scorer import TransitionScorer


class SetBuilderService:
    """Build and rebuild optimized DJ sets from playlists."""

    def __init__(
        self,
        set_repo: SetRepository,
        playlist_repo: PlaylistRepository,
        feature_repo: FeatureRepository,
    ) -> None:
        self._sets = set_repo
        self._playlists = playlist_repo
        self._features = feature_repo

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
        if await self._playlists.get_by_id(playlist_id) is None:
            raise NotFoundError("Playlist", playlist_id)
        track_ids = await self._playlists.get_track_ids(playlist_id)
        if not track_ids:
            raise ValidationError("Playlist is empty")

        # Exclude banned tracks (Phase 3 AI intelligence)
        try:
            from app.db.repositories.track_feedback import TrackFeedbackRepository

            feedback_repo = TrackFeedbackRepository(self._playlists.session)
            banned = set(await feedback_repo.get_banned_ids())
            if banned:
                track_ids = [tid for tid in track_ids if tid not in banned]
        except Exception:
            pass  # Feedback exclusion is non-critical

        features_map = await self._features.get_scoring_features_batch(track_ids)
        track_features_list = [features_map.get(tid, TrackFeatures()) for tid in track_ids]

        optimized_order, quality, used_algorithm = self._optimize_order(
            track_ids,
            track_features_list,
            algorithm,
            template_name=template,
        )

        dj_set = DjSet(
            name=name,
            target_duration_ms=(target_duration_min * 60_000) if target_duration_min else None,
            template_name=template,
            source_playlist_id=playlist_id,
        )
        dj_set = await self._sets.create(dj_set)

        from app.core.utils.time import utc_timestamp_iso

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

        # Persist quality score to the version
        if quality is not None:
            version.quality_score = quality
            await self._sets.session.flush()

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
            template_name=template,
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
        algorithm: str = "greedy",
    ) -> SetVersion:
        """Rebuild existing set with pin/exclude. Creates new version."""
        latest = await self._sets.get_latest_version(set_id)
        if latest is None:
            raise NotFoundError("SetVersion", f"set_id={set_id}")

        current_ids = [item.track_id for item in await self._sets.get_version_items(latest.id)]
        dj_set = await self._sets.get_by_id(set_id)
        template_name = dj_set.template_name if dj_set is not None else None

        exclude_set = set(exclude_tracks or [])
        filtered = [tid for tid in current_ids if tid not in exclude_set]

        # Re-optimize the filtered track set so the new version has a quality score
        # comparable to build_set.
        features_map = await self._features.get_scoring_features_batch(filtered)
        track_features_list = [features_map.get(tid, TrackFeatures()) for tid in filtered]
        optimized_order, quality, _ = self._optimize_order(
            filtered,
            track_features_list,
            algorithm,
            template_name=template_name,
        )

        pinned_set = set(pin_tracks or [])
        label = version_label or f"v{latest.id + 1}"

        items = [
            {
                "track_id": tid,
                "sort_index": idx,
                "pinned": tid in pinned_set,
            }
            for idx, tid in enumerate(optimized_order)
        ]
        version = await self._sets.create_version_with_items(set_id, items, label=label)

        if quality is not None:
            version.quality_score = quality
            await self._sets.session.flush()

        return version

    # ── Private ──────────────────────────────────────

    @staticmethod
    def _optimize_order(
        track_ids: list[int],
        track_features_list: list[TrackFeatures],
        algorithm: str,
        template_name: str | None = None,
    ) -> tuple[list[int], float | None, str]:
        """Run optimizer and return (ordered_ids, quality_score, algorithm_used)."""
        from app.optimization.genetic import GeneticAlgorithm
        from app.optimization.greedy import GreedyChainBuilder

        scorer = TransitionScorer()
        has_features = any(f.bpm is not None for f in track_features_list)
        moods = {
            tid: features.mood
            for tid, features in zip(track_ids, track_features_list, strict=False)
        }

        template = None
        if template_name:
            try:
                template = get_template(template_name)
            except KeyError:
                template = None

        if not has_features:
            return track_ids, None, "playlist_order"

        if algorithm in ("ga", "genetic"):
            ga = GeneticAlgorithm(scorer)
            opt_result = ga.optimize(
                track_features_list,
                track_ids,
                template=template,
                moods=moods,
            )
        else:
            builder = GreedyChainBuilder(scorer)
            opt_result = builder.optimize(
                track_features_list,
                track_ids,
                template=template,
                moods=moods,
            )

        return opt_result.track_order, opt_result.quality_score, algorithm

    # ── Library mode ─────────────────────────────────

    async def build_set_from_library(
        self,
        name: str,
        *,
        template: str | None = None,
        bpm_min: float | None = None,
        bpm_max: float | None = None,
        moods: list[str] | None = None,
        energy_min: float | None = None,
        energy_max: float | None = None,
        pool_size: int = 500,
        target_duration_min: int | None = None,
        algorithm: str = "greedy",
    ) -> tuple[DjSet, SetVersion, float | None, str]:
        """Build optimized set from the full track library.

        Uses SQL filtering to select a candidate pool, then runs
        the same greedy/GA optimization as playlist-based builds.
        No MP3 downloads — works entirely on existing L2+ features.

        Returns (dj_set, version, quality_score, algorithm_used).
        """
        # Derive filter bounds from template slots (if any)
        tmpl_filters = self._template_filters(template) if template else {}
        eff_bpm_min = bpm_min if bpm_min is not None else tmpl_filters.get("bpm_min")
        eff_bpm_max = bpm_max if bpm_max is not None else tmpl_filters.get("bpm_max")
        eff_moods = moods if moods is not None else tmpl_filters.get("moods")

        # Exclude banned tracks
        banned: set[int] = set()
        try:
            from app.db.repositories.track_feedback import TrackFeedbackRepository

            feedback_repo = TrackFeedbackRepository(self._features.session)
            banned = set(await feedback_repo.get_banned_ids())
        except Exception:
            pass

        # SQL-filtered candidate pool from entire library
        track_ids = await self._features.get_library_candidates(
            bpm_min=eff_bpm_min,
            bpm_max=eff_bpm_max,
            moods=eff_moods,
            energy_min=energy_min,
            energy_max=energy_max,
            exclude_ids=banned or None,
            pool_size=pool_size,
        )
        if not track_ids:
            raise ValidationError("No tracks match the filters. Try widening BPM range or moods.")

        # Load features & optimize (same path as playlist mode)
        features_map = await self._features.get_scoring_features_batch(track_ids)
        track_features_list = [features_map.get(tid, TrackFeatures()) for tid in track_ids]

        optimized_order, quality, used_algorithm = self._optimize_order(
            track_ids,
            track_features_list,
            algorithm,
            template_name=template,
        )

        # Truncate by target duration — keep only tracks that fit
        if target_duration_min:
            target_ms = target_duration_min * 60_000
            # Load durations from tracks table
            from sqlalchemy import select as sa_select

            from app.db.models.track import Track

            dur_stmt = sa_select(Track.id, Track.duration_ms).where(Track.id.in_(optimized_order))
            dur_result = await self._sets.session.execute(dur_stmt)
            dur_map = {r[0]: r[1] or 300_000 for r in dur_result.all()}

            truncated: list[int] = []
            cumulative_ms = 0
            for tid in optimized_order:
                dur = dur_map.get(tid, 300_000)  # fallback 5 min
                if cumulative_ms + dur > target_ms and truncated:
                    break
                truncated.append(tid)
                cumulative_ms += dur
            optimized_order = truncated

        # Persist
        dj_set = DjSet(
            name=name,
            target_duration_ms=(target_duration_min * 60_000) if target_duration_min else None,
            template_name=template,
            source_playlist_id=None,
        )
        dj_set = await self._sets.create(dj_set)

        from app.core.utils.time import utc_timestamp_iso

        gen_meta = _json.dumps(
            {
                "source": "library",
                "algorithm": used_algorithm,
                "pool_size": len(track_ids),
                "track_count": len(optimized_order),
                "template": template,
                "filters": {
                    "bpm_min": eff_bpm_min,
                    "bpm_max": eff_bpm_max,
                    "moods": eff_moods,
                    "energy_min": energy_min,
                    "energy_max": energy_max,
                },
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

        if quality is not None:
            version.quality_score = quality
            await self._sets.session.flush()

        return dj_set, version, quality, used_algorithm

    @staticmethod
    def _template_filters(template_name: str) -> dict[str, Any]:
        """Extract aggregate BPM/mood filter bounds from template slots."""
        try:
            tmpl = get_template(template_name)
        except KeyError:
            return {}
        bpm_min = min(s.bpm_min for s in tmpl.slots) - 2
        bpm_max = max(s.bpm_max for s in tmpl.slots) + 2
        moods_set = {s.target_mood for s in tmpl.slots if s.target_mood}
        return {
            "bpm_min": bpm_min,
            "bpm_max": bpm_max,
            "moods": list(moods_set) if moods_set else None,
        }
