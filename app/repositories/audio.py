"""Audio analysis repository — DB operations for audio pipeline."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio import FeatureExtractionRun, TrackAudioFeaturesComputed
from app.models.library import DjLibraryItem
from app.models.track import Track
from app.repositories.base import BaseRepository


class AudioRepository(BaseRepository[TrackAudioFeaturesComputed]):
    """Repository for audio analysis DB operations.

    Extracted from AudioService to enforce Tools -> Services -> Repos -> Models.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TrackAudioFeaturesComputed)

    async def get_track(self, track_id: int) -> Track | None:
        """Return a track by ID, or ``None``."""
        stmt = select(Track).where(Track.id == track_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_features_by_track_id(self, track_id: int) -> TrackAudioFeaturesComputed | None:
        """Return computed audio features for a track, or ``None``."""
        stmt = select(TrackAudioFeaturesComputed).where(
            TrackAudioFeaturesComputed.track_id == track_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_library_item_by_track_id(self, track_id: int) -> DjLibraryItem | None:
        """Return the library item (audio file) for a track, or ``None``."""
        stmt = select(DjLibraryItem).where(DjLibraryItem.track_id == track_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_features(
        self,
        track_id: int,
        features_dict: dict[str, Any],
        pipeline_run_id: int,
    ) -> TrackAudioFeaturesComputed:
        """Create and persist a TrackAudioFeaturesComputed record."""
        features = TrackAudioFeaturesComputed(
            track_id=track_id,
            pipeline_run_id=pipeline_run_id,
            **features_dict,
        )
        self.session.add(features)
        await self.session.flush()
        return features

    async def delete_features(self, track_id: int) -> None:
        """Delete existing features for a track (for force re-analysis)."""
        existing = await self.get_features_by_track_id(track_id)
        if existing:
            await self.session.delete(existing)
            await self.session.flush()

    async def create_pipeline_run(
        self,
        track_id: int,
        name: str,
        version: str,
        status: str = "completed",
    ) -> FeatureExtractionRun:
        """Create a FeatureExtractionRun record."""
        run = FeatureExtractionRun(
            track_id=track_id,
            pipeline_name=name,
            pipeline_version=version,
            status=status,
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def update_mood(
        self,
        features: TrackAudioFeaturesComputed,
        mood: str,
        confidence: float,
    ) -> None:
        """Update mood classification on existing features."""
        features.mood = mood
        features.mood_confidence = confidence
        await self.session.flush()
