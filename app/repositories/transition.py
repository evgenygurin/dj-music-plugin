"""Transition repository."""

from __future__ import annotations

from typing import Any

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

    async def upsert(
        self,
        *,
        from_track_id: int,
        to_track_id: int,
        **fields: Any,
    ) -> Transition:
        """Insert or update the transition row for ``(from_track_id, to_track_id)``.

        Used by ``transition_persist_handler`` so that re-scoring a pair
        replaces the prior row instead of accumulating duplicates.
        """
        existing = await self.get_pair(from_track_id, to_track_id)
        if existing is None:
            return await self.create(
                from_track_id=from_track_id,
                to_track_id=to_track_id,
                **fields,
            )
        for key, value in fields.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        await self.session.flush()
        await self.session.refresh(existing)
        return existing

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

    async def list_from(self, from_track_id: int, *, limit: int = 30) -> list[Transition]:
        """All persisted transitions originating at ``from_track_id``,
        best-quality-first.

        Audit iter 37 (T-35): ``local://tracks/{id}/suggest_next``
        wanted to read this method via ``getattr(uow.transitions,
        "list_from", None)``; the resource has shipped since v1.0
        always returning the placeholder reason "transitions
        repository does not expose list_from yet" — i.e. the
        suggestion path was effectively dead even for tracks that
        have logged transitions.

        Order:
        - ``overall_quality DESC NULLS LAST`` (best score first; Postgres
          orders NULL ahead of values in DESC by default, which would
          push hard-rejects to the top — explicit nulls_last avoids it
          and SQLite ignores the hint cleanly)
        - tiebreaker on ``id DESC`` so newer scoring runs win on equal
          quality.
        """
        stmt = (
            select(Transition)
            .where(Transition.from_track_id == from_track_id)
            .order_by(Transition.overall_quality.desc().nulls_last(), Transition.id.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())
