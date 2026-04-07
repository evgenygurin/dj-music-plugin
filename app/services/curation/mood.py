"""Mood classification sub-service."""

from __future__ import annotations

from typing import Any

from app.audio.classification import MoodClassifier
from app.core.errors import ValidationError
from app.repositories.feature import FeatureRepository
from app.repositories.playlist import PlaylistRepository


class MoodClassificationService:
    """Classify tracks by 15 techno subgenres."""

    def __init__(
        self,
        feature_repo: FeatureRepository,
        playlist_repo: PlaylistRepository,
    ) -> None:
        self._features = feature_repo
        self._playlists = playlist_repo

    async def classify_mood(
        self,
        track_ids: list[int] | None = None,
        playlist_id: int | None = None,
        reclassify: bool = False,
    ) -> dict[str, Any]:
        """Classify tracks by 15 techno subgenres."""
        ids_to_classify: list[int] = list(track_ids or [])
        if playlist_id is not None:
            playlist_track_ids = await self._playlists.get_track_ids(playlist_id)
            ids_to_classify.extend(playlist_track_ids)

        if not ids_to_classify:
            raise ValidationError("No tracks to classify")

        classifier = MoodClassifier()
        classifications: list[dict[str, Any]] = []
        skipped_no_features = 0
        skipped_already_classified = 0

        # Batch-load features for all tracks (N queries → 1)
        features_map = await self._features.get_features_batch(ids_to_classify)

        for tid in ids_to_classify:
            features = features_map.get(tid)
            if features is None:
                skipped_no_features += 1
                continue

            if not reclassify and features.mood is not None:
                skipped_already_classified += 1
                continue

            feat_dict = features.to_classifier_dict()
            mood_result = classifier.classify(feat_dict)

            # Persist mood to DB so it's queryable via SQL
            features.mood = mood_result.mood.value
            features.mood_confidence = mood_result.confidence

            classifications.append(
                {
                    "track_id": tid,
                    "mood": mood_result.mood.value,
                    "confidence": round(mood_result.confidence, 3),
                    "reasoning": mood_result.reasoning,
                    "top_3": [
                        {"subgenre": sg.value, "score": round(sc, 3)}
                        for sg, sc in sorted(
                            mood_result.scores.items(), key=lambda x: x[1], reverse=True
                        )[:3]
                    ],
                }
            )

        mood_counts: dict[str, int] = {}
        for c in classifications:
            mood = c["mood"]
            mood_counts[mood] = mood_counts.get(mood, 0) + 1

        return {
            "classified": len(classifications),
            "skipped_no_features": skipped_no_features,
            "skipped_already_classified": skipped_already_classified,
            "total": len(ids_to_classify),
            "distribution": mood_counts,
            "tracks": classifications,
        }
