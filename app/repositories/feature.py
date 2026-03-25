"""Audio feature repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio import TrackAudioFeaturesComputed
from app.models.track import Track
from app.repositories.base import BaseRepository

if TYPE_CHECKING:
    from app.services.transition import TrackFeatures


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

    async def save_features(
        self, features: TrackAudioFeaturesComputed
    ) -> TrackAudioFeaturesComputed:
        """Persist audio features (add + flush)."""
        self.session.add(features)
        await self.session.flush()
        return features

    async def get_scoring_features(self, track_id: int) -> TrackFeatures | None:
        """Load features and convert to TrackFeatures for transition scoring."""
        from app.services.transition import TrackFeatures

        row = await self.get_features(track_id)
        if row is None:
            return None
        return TrackFeatures.from_db(row)

    async def get_scoring_features_batch(self, track_ids: list[int]) -> dict[int, TrackFeatures]:
        """Load TrackFeatures for multiple tracks in one query (N queries → 1)."""
        from app.services.transition import TrackFeatures

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
