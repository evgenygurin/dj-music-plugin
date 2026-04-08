"""Transition repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.transition import Transition, TransitionCandidate
from app.db.repositories.base import BaseRepository


class TransitionRepository(BaseRepository[Transition]):
    """Repository for :class:`Transition` with candidate lookups."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Transition)

    async def get_score(self, from_id: int, to_id: int) -> Transition | None:
        """Return the transition score between two tracks, or ``None``."""
        stmt = select(Transition).where(
            Transition.from_track_id == from_id,
            Transition.to_track_id == to_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_score(self, transition: Transition) -> Transition:
        """Persist a transition score (add + flush)."""
        self.session.add(transition)
        await self.session.flush()
        return transition

    async def get_candidates(self, track_id: int, limit: int = 10) -> list[TransitionCandidate]:
        """Return transition candidates from a given track."""
        stmt = (
            select(TransitionCandidate)
            .where(TransitionCandidate.from_track_id == track_id)
            .order_by(TransitionCandidate.id)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
