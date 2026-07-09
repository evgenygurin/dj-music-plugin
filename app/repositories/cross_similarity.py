from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cross_similarity import CrossSimilarity


class CrossSimilarityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self, track_a_id: int, track_b_id: int, stem_name: str, data: dict[str, Any]
    ) -> CrossSimilarity:
        row = CrossSimilarity(
            track_a_id=track_a_id, track_b_id=track_b_id, stem_name=stem_name, **data
        )
        await self._session.merge(row)
        await self._session.flush()
        return row

    async def get_for_pair(
        self, track_a_id: int, track_b_id: int, stem_name: str = "original"
    ) -> CrossSimilarity | None:
        result = await self._session.scalars(
            select(CrossSimilarity).where(
                CrossSimilarity.track_a_id == track_a_id,
                CrossSimilarity.track_b_id == track_b_id,
                CrossSimilarity.stem_name == stem_name,
            )
        )
        return result.first()
