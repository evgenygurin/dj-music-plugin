"""Audio analysis repository — DB operations for audio pipeline."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio import (
    FeatureExtractionRun,
    TimeseriesReference,
    TrackAudioFeaturesComputed,
    TrackSection,
)
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

    async def create_features_from_pipeline(
        self,
        track_id: int,
        features_dict: dict[str, Any],
        pipeline_run_id: int,
    ) -> TrackAudioFeaturesComputed:
        """Create features from pipeline analysis results."""
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

    async def get_tracks_below_level(self, track_ids: list[int], target_level: int) -> list[int]:
        """Return track IDs that need analysis at target level.

        Includes IDs with analysis_level < target_level AND IDs with no features row.
        """
        if not track_ids:
            return []
        stmt = select(TrackAudioFeaturesComputed.track_id).where(
            TrackAudioFeaturesComputed.track_id.in_(track_ids),
            TrackAudioFeaturesComputed.analysis_level >= target_level,
        )
        result = await self.session.execute(stmt)
        already_done = {row[0] for row in result.all()}
        return [tid for tid in track_ids if tid not in already_done]

    async def save_or_update_features(
        self,
        track_id: int,
        features_dict: dict[str, Any],
        level: int,
    ) -> TrackAudioFeaturesComputed:
        """Create or update features row, merging new features and setting analysis_level."""
        existing = await self.get_features_by_track_id(track_id)
        filtered = TrackAudioFeaturesComputed.filter_features(features_dict)

        if existing:
            for key, value in filtered.items():
                if value is not None:
                    setattr(existing, key, value)
            existing.analysis_level = max(existing.analysis_level, level)
            await self.session.flush()
            return existing

        row = TrackAudioFeaturesComputed(track_id=track_id, analysis_level=level, **filtered)
        self.session.add(row)
        await self.session.flush()
        return row

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

    async def save_sections(self, track_id: int, sections: list[dict[str, Any]]) -> None:
        """Persist track sections (idempotent: deletes existing first)."""
        # Delete existing sections for this track
        stmt = select(TrackSection).where(TrackSection.track_id == track_id)
        result = await self.session.execute(stmt)
        for existing in result.scalars().all():
            await self.session.delete(existing)
        await self.session.flush()

        # Create new sections
        for s in sections:
            section = TrackSection(
                track_id=track_id,
                section_type=s.get("section_type", 0),
                start_ms=s.get("start_ms", 0),
                end_ms=s.get("end_ms", 0),
                energy=s.get("energy"),
                confidence=s.get("confidence"),
            )
            self.session.add(section)
        await self.session.flush()

    async def save_timeseries_reference(
        self, track_id: int, metadata: dict[str, Any]
    ) -> TimeseriesReference:
        """Create a TimeseriesReference row from storage metadata."""
        ref = TimeseriesReference(
            track_id=track_id,
            feature_set_name=metadata["feature_set_name"],
            storage_uri=metadata["storage_uri"],
            frame_count=metadata["frame_count"],
            hop_length=metadata["hop_length"],
            sample_rate=metadata["sample_rate"],
            data_type=metadata.get("data_type", "float32"),
            shape=metadata.get("shape", "[]"),
        )
        self.session.add(ref)
        await self.session.flush()
        return ref

    async def get_timeseries_references(self, track_id: int) -> list[TimeseriesReference]:
        """Return all timeseries references for a track."""
        stmt = select(TimeseriesReference).where(TimeseriesReference.track_id == track_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
