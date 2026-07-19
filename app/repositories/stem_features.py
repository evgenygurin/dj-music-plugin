from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.models.stem_features import StemFeatures
from app.repositories.base import BaseRepository


class StemFeaturesRepository(BaseRepository[StemFeatures]):
    model = StemFeatures

    async def upsert(
        self, track_id: int, stem_name: str, features: dict[str, Any]
    ) -> StemFeatures:
        clean = StemFeatures.filter_features(features)
        existing = await self.session.scalar(
            select(StemFeatures).where(
                StemFeatures.track_id == track_id,
                StemFeatures.stem_name == stem_name,
            )
        )
        if existing is not None:
            for key, val in clean.items():
                setattr(existing, key, val)
            await self.session.flush()
            return existing
        row = StemFeatures(track_id=track_id, stem_name=stem_name, **clean)
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_all_for_track(self, track_id: int) -> list[StemFeatures]:
        result = await self.session.scalars(
            select(StemFeatures).where(StemFeatures.track_id == track_id)
        )
        return list(result.all())
