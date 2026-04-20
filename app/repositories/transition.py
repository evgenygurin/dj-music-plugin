"""Transition repository."""

from __future__ import annotations

from sqlalchemy import select, tuple_

from app.models.transition import Transition
from app.repositories.base import BaseRepository


class TransitionRepository(BaseRepository[Transition]):
    model = Transition

    async def get_pair(self, from_track_id: int, to_track_id: int) -> Transition | None:
        stmt = (
            select(Transition)
            .where(
                Transition.from_track_id == from_track_id,
                Transition.to_track_id == to_track_id,
            )
            .order_by(Transition.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)  # type: ignore[no-any-return]

    async def get_pairs_batch(
        self, pairs: list[tuple[int, int]]
    ) -> dict[tuple[int, int], Transition]:
        """Batch-fetch directed transition rows by ``(from, to)`` pairs.

        Returns the most recent ``Transition`` per pair (MAX(id) wins, matching
        ``get_pair``). Missing pairs are simply absent from the result.

        Avoids the N+1 of ``await uow.transitions.get_pair(a, b)`` inside a
        per-edge loop in set/transition rendering tools.
        """
        if not pairs:
            return {}
        stmt = (
            select(Transition)
            .where(tuple_(Transition.from_track_id, Transition.to_track_id).in_(pairs))
            .order_by(Transition.id.asc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        # Newer rows overwrite older ones because we ordered ascending —
        # last-write-wins yields MAX(id) per pair, same as ``get_pair``.
        result: dict[tuple[int, int], Transition] = {}
        for row in rows:
            result[(row.from_track_id, row.to_track_id)] = row
        return result

    # Alias used by set-review / transitions resources.
    get_by_pair = get_pair
