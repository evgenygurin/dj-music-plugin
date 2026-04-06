"""Subgenre distribution sub-service."""

from __future__ import annotations

from typing import Any

from app.audio.classification import MoodClassifier
from app.core.constants import TechnoSubgenre
from app.core.errors import ValidationError
from app.repositories.feature import FeatureRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.track import TrackRepository


class DistributionService:
    """Distribute tracks to 15 subgenre playlists based on mood."""

    def __init__(
        self,
        track_repo: TrackRepository,
        playlist_repo: PlaylistRepository,
        feature_repo: FeatureRepository,
    ) -> None:
        self._tracks = track_repo
        self._playlists = playlist_repo
        self._features = feature_repo

    async def distribute_to_subgenres(
        self,
        source_playlist_id: int | None = None,
        mode: str = "append",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Distribute tracks to 15 subgenre playlists based on mood."""
        if source_playlist_id is not None:
            track_ids = await self._playlists.get_track_ids(source_playlist_id)
        else:
            track_ids = await self._tracks.get_active_track_ids()

        if not track_ids:
            raise ValidationError("No tracks to distribute")

        classifier = MoodClassifier()
        distribution: dict[str, list[int]] = {sg.value: [] for sg in TechnoSubgenre}
        skipped = 0

        for tid in track_ids:
            features = await self._features.get_features(tid)
            if features is None:
                skipped += 1
                continue
            feat_dict = features.to_classifier_dict()
            mood_result = classifier.classify(feat_dict)
            # Persist mood to DB
            features.mood = mood_result.mood.value
            features.mood_confidence = mood_result.confidence
            distribution[mood_result.mood.value].append(tid)

        if dry_run:
            summary = {sg: len(ids) for sg, ids in distribution.items() if ids}
            return {
                "dry_run": True,
                "total_tracks": len(track_ids),
                "classified": len(track_ids) - skipped,
                "skipped_no_features": skipped,
                "distribution": summary,
            }

        created_playlists = 0
        total_assigned = 0

        for subgenre in TechnoSubgenre:
            sg_track_ids = distribution[subgenre.value]
            if not sg_track_ids:
                continue

            playlist_name = f"Subgenre: {subgenre.value}"
            playlist, is_new = await self._playlists.get_or_create_by_name(playlist_name)
            if is_new:
                created_playlists += 1

            if mode == "clean_rebuild":
                await self._playlists.clear_items(playlist.id)
                start_idx = 0
            else:
                start_idx = await self._playlists.get_max_sort_index(playlist.id) + 1

            for i, tid in enumerate(sg_track_ids):
                await self._playlists.add_track(playlist.id, tid, start_idx + i)
                total_assigned += 1

        summary = {sg: len(ids) for sg, ids in distribution.items() if ids}

        return {
            "total_tracks": len(track_ids),
            "classified": len(track_ids) - skipped,
            "skipped_no_features": skipped,
            "created_playlists": created_playlists,
            "total_assigned": total_assigned,
            "distribution": summary,
            "synced_to_ym": False,
        }
