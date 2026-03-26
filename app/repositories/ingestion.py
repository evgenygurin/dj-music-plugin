"""Ingestion repository — cache raw provider API responses."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion import RawProviderResponse
from app.utils.time import utc_now


class IngestionRepository:
    """Data access for raw provider response caching."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_cached_response(
        self,
        track_id: int,
        provider_name: str,
    ) -> dict[str, Any] | None:
        """Get cached raw response for a track+provider. Returns parsed JSON or None."""
        provider_id = await self._resolve_provider_id(provider_name)
        if provider_id is None:
            return None

        stmt = select(RawProviderResponse).where(
            RawProviderResponse.track_id == track_id,
            RawProviderResponse.provider_id == provider_id,
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None or not row.raw_data:
            return None

        return json.loads(row.raw_data)

    async def cache_response(
        self,
        track_id: int,
        provider_name: str,
        raw_data: dict[str, Any],
    ) -> RawProviderResponse | None:
        """Cache a raw API response. Returns the created row, or None if provider not found."""
        provider_id = await self._ensure_provider_id(provider_name)

        # Upsert: check if existing
        stmt = select(RawProviderResponse).where(
            RawProviderResponse.track_id == track_id,
            RawProviderResponse.provider_id == provider_id,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.raw_data = json.dumps(raw_data, ensure_ascii=False, default=str)
            existing.fetched_at = utc_now()
            await self.session.flush()
            return existing

        row = RawProviderResponse(
            track_id=track_id,
            provider_id=provider_id,
            raw_data=json.dumps(raw_data, ensure_ascii=False, default=str),
            fetched_at=utc_now(),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def _resolve_provider_id(self, provider_name: str) -> int | None:
        """Resolve provider name to ID. Returns None if not found."""
        from app.models.ingestion import ProviderModel

        stmt = select(ProviderModel.id).where(ProviderModel.name == provider_name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _ensure_provider_id(self, provider_name: str) -> int:
        """Resolve provider name to ID, creating it if needed."""
        from app.models.ingestion import ProviderModel

        existing = await self._resolve_provider_id(provider_name)
        if existing is not None:
            return existing

        provider = ProviderModel(name=provider_name)
        self.session.add(provider)
        await self.session.flush()
        return provider.id
