"""TransitionHistory repository."""

from __future__ import annotations

from sqlalchemy import desc, func, select

from app.v2.models.transition_history import TransitionHistory
from app.v2.repositories.base import BaseRepository


class TransitionHistoryRepository(BaseRepository[TransitionHistory]):
    model = TransitionHistory

    async def best_pairs(self, limit: int = 20) -> list[TransitionHistory]:
        stmt = (
            select(TransitionHistory).order_by(desc(TransitionHistory.overall_score)).limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def reaction_counts(self) -> dict[str, int]:
        stmt = select(TransitionHistory.reaction, func.count()).group_by(
            TransitionHistory.reaction
        )
        return {r or "none": n for r, n in (await self.session.execute(stmt)).all()}
