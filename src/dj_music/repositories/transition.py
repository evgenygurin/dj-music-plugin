"""Transition repository."""

from sqlalchemy import or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from dj_music.models.transition import Transition, TransitionCandidate
from dj_music.repositories.base import BaseRepository


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

    async def get_scores_batch(
        self,
        pairs: list[tuple[int, int]],
    ) -> dict[tuple[int, int], Transition]:
        """Return all existing transition scores for the given pairs in one query.

        Maps ``(from_track_id, to_track_id)`` → :class:`Transition`. Missing
        pairs are simply absent from the result. Enables O(1) cache lookups in
        bulk scoring loops without N database round-trips.
        """
        if not pairs:
            return {}
        stmt = select(Transition).where(
            tuple_(Transition.from_track_id, Transition.to_track_id).in_(pairs)
        )
        result = await self.session.execute(stmt)
        return {(row.from_track_id, row.to_track_id): row for row in result.scalars().all()}

    async def get_scores_for_seed(
        self,
        seed_track_id: int,
        candidate_ids: list[int],
    ) -> dict[int, Transition]:
        """Return cached transitions where ``seed_track_id`` is either endpoint.

        Returns a map of ``other_track_id`` → :class:`Transition`. Matches
        both ``seed → candidate`` and ``candidate → seed`` directions so that
        speculative prefetch can skip any pair already scored once.
        """
        if not candidate_ids:
            return {}
        stmt = select(Transition).where(
            or_(
                (Transition.from_track_id == seed_track_id)
                & Transition.to_track_id.in_(candidate_ids),
                (Transition.to_track_id == seed_track_id)
                & Transition.from_track_id.in_(candidate_ids),
            )
        )
        result = await self.session.execute(stmt)
        out: dict[int, Transition] = {}
        for row in result.scalars().all():
            other = row.to_track_id if row.from_track_id == seed_track_id else row.from_track_id
            out[other] = row
        return out

    async def save_score(self, transition: Transition) -> Transition:
        """Persist a transition score (add + flush)."""
        self.session.add(transition)
        await self.session.flush()
        return transition

    async def save_scores_bulk(self, transitions: list[Transition]) -> int:
        """Persist many transition scores in a single flush.

        Skips the N-round-trip cost of calling ``save_score`` in a loop when
        the parallel scorer computes many pairs at once. Returns the count of
        rows added to the session.
        """
        if not transitions:
            return 0
        self.session.add_all(transitions)
        await self.session.flush()
        return len(transitions)

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
