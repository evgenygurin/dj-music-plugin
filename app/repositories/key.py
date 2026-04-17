"""Key reference repository."""

from __future__ import annotations

from sqlalchemy import select

from app.models.key import Key, KeyEdge
from app.repositories.base import BaseRepository


class KeyRepository(BaseRepository[Key]):
    model = Key

    async def get_by_camelot(self, camelot: str) -> Key | None:
        return await self.session.scalar(  # type: ignore[no-any-return]
            select(Key).where(Key.camelot == camelot).limit(1)
        )


class KeyEdgeRepository(BaseRepository[KeyEdge]):
    model = KeyEdge

    async def edges_from(self, from_key: int) -> list[KeyEdge]:
        stmt = select(KeyEdge).where(KeyEdge.from_key == from_key).order_by(KeyEdge.distance)
        return list((await self.session.execute(stmt)).scalars())
