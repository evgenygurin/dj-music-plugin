"""Transition history repository."""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models.track import Track
from app.db.models.transition_history import TransitionHistory
from app.db.repositories.base import BaseRepository


class TransitionHistoryRepository(BaseRepository[TransitionHistory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TransitionHistory)

    async def ensure_tracks_exist(self, track_ids: list[int]) -> None:
        """Raise NotFoundError if any track_id is missing from the DB."""
        result = await self.session.execute(select(Track.id).where(Track.id.in_(track_ids)))
        found = set(result.scalars().all())
        missing = set(track_ids) - found
        if missing:
            raise NotFoundError("Track", sorted(missing)[0])

    async def log(self, entry: TransitionHistory) -> TransitionHistory:
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_history(
        self,
        from_track_id: int | None = None,
        to_track_id: int | None = None,
        limit: int = 20,
        min_score: float | None = None,
    ) -> list[TransitionHistory]:
        stmt = select(TransitionHistory).order_by(desc(TransitionHistory.created_at))
        if from_track_id is not None:
            stmt = stmt.where(TransitionHistory.from_track_id == from_track_id)
        if to_track_id is not None:
            stmt = stmt.where(TransitionHistory.to_track_id == to_track_id)
        if min_score is not None:
            stmt = stmt.where(TransitionHistory.overall_score >= min_score)
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_best_pairs(self, track_id: int, limit: int = 10) -> list[dict[str, Any]]:
        stmt = (
            select(
                TransitionHistory.to_track_id.label("track_id"),
                func.count().label("play_count"),
                func.avg(TransitionHistory.overall_score).label("avg_score"),
                func.max(TransitionHistory.user_reaction).label("last_reaction"),
            )
            .where(TransitionHistory.from_track_id == track_id)
            .where(
                (TransitionHistory.user_reaction != "ban")
                | (TransitionHistory.user_reaction.is_(None))
            )
            .group_by(TransitionHistory.to_track_id)
            .order_by(desc("avg_score"))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [dict(row._mapping) for row in result.all()]

    async def get_pair_reaction(self, from_id: int, to_id: int) -> str | None:
        stmt = (
            select(TransitionHistory.user_reaction)
            .where(TransitionHistory.from_track_id == from_id)
            .where(TransitionHistory.to_track_id == to_id)
            .where(TransitionHistory.user_reaction.isnot(None))
            .order_by(desc(TransitionHistory.created_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_reaction(self, entry_id: int, reaction: str) -> None:
        entry = await self.get_by_id(entry_id)
        if entry is None:
            raise NotFoundError("TransitionHistory", entry_id)
        entry.user_reaction = reaction
        await self.session.flush()
