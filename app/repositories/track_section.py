from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from app.models.track_features import TrackSection
from app.repositories.base import BaseRepository


class TrackSectionRepository(BaseRepository[TrackSection]):
    model = TrackSection

    async def list_by_track(self, track_id: int) -> Sequence[TrackSection]:
        stmt = select(TrackSection).where(TrackSection.track_id == track_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()
