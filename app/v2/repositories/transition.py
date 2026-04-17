"""Transition repository."""

from __future__ import annotations

from sqlalchemy import select

from app.v2.models.transition import Transition
from app.v2.repositories.base import BaseRepository


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
