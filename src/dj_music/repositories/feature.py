"""Audio feature repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dj_music.models.audio import TrackAudioFeaturesComputed, TrackSection
from dj_music.models.track import Track
from dj_music.schemas.audio import TrackFeatures
from dj_music.repositories.base import BaseRepository


class FeatureRepository(BaseRepository[TrackAudioFeaturesComputed]):
    """Repository for :class:`TrackAudioFeaturesComputed`."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TrackAudioFeaturesComputed)

    async def get_features(self, track_id: int) -> TrackAudioFeaturesComputed | None:
        """Return computed features for a track, or ``None``."""
        stmt = select(TrackAudioFeaturesComputed).where(
            TrackAudioFeaturesComputed.track_id == track_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_features_batch(
        self, track_ids: list[int]
    ) -> dict[int, TrackAudioFeaturesComputed]:
        """Return raw ``TrackAudioFeaturesComputed`` rows keyed by ``track_id``.

        Single SQL ``IN (...)`` query — used by ``list_tracks`` /
        ``filter_tracks`` to render BPM/key/LUFS columns without
        per-row N+1 lookups. Tracks without features are simply absent
        from the returned mapping.
        """
        if not track_ids:
            return {}
        stmt = select(TrackAudioFeaturesComputed).where(
            TrackAudioFeaturesComputed.track_id.in_(track_ids)
        )
        result = await self.session.execute(stmt)
        return {row.track_id: row for row in result.scalars().all()}

    async def save_features(
        self, features: TrackAudioFeaturesComputed
    ) -> TrackAudioFeaturesComputed:
        """Persist audio features (add + flush)."""
        self.session.add(features)
        await self.session.flush()
        return features

    async def get_scoring_features(self, track_id: int) -> TrackFeatures | None:
        """Load features and convert to TrackFeatures for transition scoring."""
        row = await self.get_features(track_id)
        if row is None:
            return None
        return TrackFeatures.from_db(row)

    async def get_scoring_features_batch(self, track_ids: list[int]) -> dict[int, TrackFeatures]:
        """Load TrackFeatures for multiple tracks in one query (N queries → 1)."""
        stmt = select(TrackAudioFeaturesComputed).where(
            TrackAudioFeaturesComputed.track_id.in_(track_ids)
        )
        result = await self.session.execute(stmt)
        return {row.track_id: TrackFeatures.from_db(row) for row in result.scalars().all()}

    async def get_tracks_without_features(self, limit: int = 50) -> list[Track]:
        """Return tracks that have no computed audio features yet."""
        subq = select(TrackAudioFeaturesComputed.track_id)
        stmt = select(Track).where(~Track.id.in_(subq)).order_by(Track.id).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_sections(self, track_id: int) -> list[TrackSection]:
        """Return track sections ordered by start time."""
        stmt = (
            select(TrackSection)
            .where(TrackSection.track_id == track_id)
            .order_by(TrackSection.start_ms)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_track_ids_with_features(self) -> list[int]:
        """Return all track IDs that have computed audio features."""
        stmt = select(TrackAudioFeaturesComputed.track_id).order_by(
            TrackAudioFeaturesComputed.track_id
        )
        result = await self.session.execute(stmt)
        return [r[0] for r in result.all()]
