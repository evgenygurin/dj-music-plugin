"""TrackFeedback repository — single row per track keyed by ``track_id``."""

from __future__ import annotations

from sqlalchemy import select

from app.models.track_feedback import TrackFeedback
from app.repositories.base import BaseRepository


class TrackFeedbackRepository(BaseRepository[TrackFeedback]):
    model = TrackFeedback

    async def list_by_status(self, status: str, limit: int = 100) -> list[TrackFeedback]:
        """Return up to ``limit`` rows whose ``status`` matches.

        Replaces the prior ``list_by_kind`` (the column was renamed to
        ``status`` in the prod schema sync 2026-05-07).
        """
        stmt = select(TrackFeedback).where(TrackFeedback.status == status).limit(limit)
        return list((await self._execute(stmt)).scalars())

    async def for_track(self, track_id: int) -> TrackFeedback | None:
        """Return the single feedback row for ``track_id`` (table is
        UNIQUE on ``track_id``) or ``None``."""
        stmt = select(TrackFeedback).where(TrackFeedback.track_id == track_id)
        return await self.session.scalar(stmt)  # type: ignore[no-any-return]
