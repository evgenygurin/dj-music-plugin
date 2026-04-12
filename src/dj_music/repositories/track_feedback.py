"""Track feedback repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dj_music.models.track_feedback import TrackFeedback
from dj_music.repositories.base import BaseRepository


class TrackFeedbackRepository(BaseRepository[TrackFeedback]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TrackFeedback)

    async def get_by_track(self, track_id: int) -> TrackFeedback | None:
        stmt = select(TrackFeedback).where(TrackFeedback.track_id == track_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, track_id: int, **kwargs) -> TrackFeedback:
        existing = await self.get_by_track(track_id)
        if existing:
            for k, v in kwargs.items():
                if v is not None:
                    setattr(existing, k, v)
            await self.session.flush()
            return existing
        entry = TrackFeedback(track_id=track_id, **kwargs)
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_banned_ids(self) -> list[int]:
        stmt = select(TrackFeedback.track_id).where(TrackFeedback.status == "banned")
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_liked_ids(self) -> list[int]:
        stmt = select(TrackFeedback.track_id).where(TrackFeedback.status == "liked")
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def increment_play(self, track_id: int) -> None:
        entry = await self.get_by_track(track_id)
        if entry:
            entry.play_count += 1
            await self.session.flush()
        else:
            self.session.add(TrackFeedback(track_id=track_id, play_count=1))
            await self.session.flush()

    async def increment_skip(self, track_id: int) -> None:
        entry = await self.get_by_track(track_id)
        if entry:
            entry.skip_count += 1
            await self.session.flush()
        else:
            self.session.add(TrackFeedback(track_id=track_id, skip_count=1))
            await self.session.flush()
