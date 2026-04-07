"""Set builder sub-service — build and rebuild DJ sets."""

from __future__ import annotations

import json as _json
from typing import Any

from app.core.errors import NotFoundError, ValidationError
from app.models.set import DjSet, SetVersion
from app.repositories.feature import FeatureRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.services.transition import TrackFeatures, TransitionScorer


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
