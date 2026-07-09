from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stem_features import StemFeatures


class StemFeaturesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self, track_id: int, stem_name: str, features: dict[str, Any]
    ) -> StemFeatures:
        clean = StemFeatures.filter_features(features)
        existing = await self._session.scalar(
            select(StemFeatures).where(
                StemFeatures.track_id == track_id,
                StemFeatures.stem_name == stem_name,
            )
        )
        if existing is not None:
            for key, val in clean.items():
                setattr(existing, key, val)
            await self._session.flush()
            return existing
        row = StemFeatures(track_id=track_id, stem_name=stem_name, **clean)
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_all_for_track(self, track_id: int) -> list[StemFeatures]:
        from sqlalchemy import select

        result = await self._session.scalars(
            select(StemFeatures).where(StemFeatures.track_id == track_id)
        )
        return list(result.all())
