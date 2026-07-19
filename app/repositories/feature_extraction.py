from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.track_features import FeatureExtractionRun
from app.repositories.base import BaseRepository


class FeatureExtractionRunRepository(BaseRepository[FeatureExtractionRun]):
    model = FeatureExtractionRun

    async def create(self, **data: Any) -> FeatureExtractionRun:
        data.setdefault("status", "pending")
        data.setdefault("parameters", None)
        return await super().create(**data)

    async def update(self, id: int, **data: Any) -> FeatureExtractionRun:
        data["updated_at"] = datetime.now(UTC)
        return await super().update(id, **data)
