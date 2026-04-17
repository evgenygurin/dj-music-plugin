"""TrackFeedback repository."""

from __future__ import annotations

from sqlalchemy import select

from app.v2.models.track_feedback import TrackFeedback
from app.v2.repositories.base import BaseRepository


class TrackFeedbackRepository(BaseRepository[TrackFeedback]):
    model = TrackFeedback

    async def list_by_kind(self, kind: str, limit: int = 100) -> list[TrackFeedback]:
        stmt = select(TrackFeedback).where(TrackFeedback.kind == kind).limit(limit)
        return list((await self.session.execute(stmt)).scalars())

    async def latest_for_track(self, track_id: int) -> TrackFeedback | None:
        stmt = (
            select(TrackFeedback)
            .where(TrackFeedback.track_id == track_id)
            .order_by(TrackFeedback.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)  # type: ignore[no-any-return]
