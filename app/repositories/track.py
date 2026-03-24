"""Track repository with text search and feature-based filtering."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import CursorPage
from app.models.audio import TrackAudioFeaturesComputed
from app.models.track import Track
from app.repositories.base import BaseRepository


class TrackRepository(BaseRepository[Track]):
    """Repository for :class:`Track` with search and filtering helpers."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Track)

    async def search_by_text(self, query: str, limit: int = 10) -> list[Track]:
        """Case-insensitive search on track title using ILIKE."""
        pattern = f"%{query}%"
        stmt = select(Track).where(Track.title.ilike(pattern)).order_by(Track.id).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def filter_by_features(
        self,
        *,
        bpm_min: float | None = None,
        bpm_max: float | None = None,
        key_code: int | None = None,
        energy_min: float | None = None,
        energy_max: float | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> CursorPage[Track]:
        """Filter tracks by joining with audio features for parametric queries."""
        stmt = select(Track).join(
            TrackAudioFeaturesComputed,
            TrackAudioFeaturesComputed.track_id == Track.id,
        )

        if bpm_min is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.bpm >= bpm_min)
        if bpm_max is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.bpm <= bpm_max)
        if key_code is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.key_code == key_code)
        if energy_min is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.energy_mean >= energy_min)
        if energy_max is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.energy_mean <= energy_max)

        return await self._paginate(stmt, limit=limit, cursor=cursor)
