"""Provider + YandexMetadata + RawProviderResponse repositories."""

from __future__ import annotations

from sqlalchemy import select

from app.v2.models.provider_metadata import (
    Provider,
    RawProviderResponse,
    YandexMetadata,
)
from app.v2.repositories.base import BaseRepository


class ProviderMetadataRepository(BaseRepository[Provider]):
    model = Provider

    async def get_by_code(self, code: str) -> Provider | None:
        return await self.session.scalar(  # type: ignore[no-any-return]
            select(Provider).where(Provider.code == code).limit(1)
        )


class YandexMetadataRepository(BaseRepository[YandexMetadata]):
    model = YandexMetadata

    async def get_for_track(self, track_id: int) -> YandexMetadata | None:
        return await self.session.get(YandexMetadata, track_id)


class RawProviderResponseRepository(BaseRepository[RawProviderResponse]):
    model = RawProviderResponse
