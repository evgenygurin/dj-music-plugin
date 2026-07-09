from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update

from app.models.track_features import FeatureExtractionRun
from app.repositories.base import BaseRepository


class FeatureExtractionRunRepository(BaseRepository[FeatureExtractionRun]):
    model = FeatureExtractionRun

    async def create(
        self,
        track_id: int,
        pipeline_name: str,
        pipeline_version: str,
        status: str = "pending",
        parameters: str | None = None,
    ) -> FeatureExtractionRun:
        row = FeatureExtractionRun(
            track_id=track_id,
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            status=status,
            parameters=parameters,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def update(self, run_id: int, **values: Any) -> None:
        values["updated_at"] = datetime.now(UTC)
        stmt = (
            update(FeatureExtractionRun)
            .where(FeatureExtractionRun.id == run_id)
            .values(**values)
        )
        await self.session.execute(stmt)
        await self.session.flush()
