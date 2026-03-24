"""Audio feature repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio import TrackAudioFeaturesComputed
from app.models.track import Track
from app.repositories.base import BaseRepository


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

    async def get_tracks_without_features(self, limit: int = 50) -> list[Track]:
        """Return tracks that have no computed audio features yet."""
        subq = select(TrackAudioFeaturesComputed.track_id)
        stmt = select(Track).where(~Track.id.in_(subq)).order_by(Track.id).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
