"""Provider + YandexMetadata + RawProviderResponse repositories."""

from __future__ import annotations

from sqlalchemy import select

from app.models.provider_metadata import (
    Provider,
    RawProviderResponse,
    YandexMetadata,
)
from app.repositories.base import BaseRepository


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

    async def upsert(
        self,
        *,
        track_id: int,
        yandex_track_id: str,
        album_id: str | None = None,
        album_title: str | None = None,
        album_genre: str | None = None,
        album_year: int | None = None,
        label: str | None = None,
        duration_ms: int | None = None,
        cover_uri: str | None = None,
        explicit: bool | None = None,
    ) -> YandexMetadata:
        """Insert or update YandexMetadata row keyed by ``track_id``."""
        existing = await self.session.get(YandexMetadata, track_id)
        fields = {
            "yandex_track_id": yandex_track_id,
            "album_id": album_id,
            "album_title": album_title,
            "album_genre": album_genre,
            "album_year": album_year,
            "label": label,
            "duration_ms": duration_ms,
            "cover_uri": cover_uri,
            "explicit": explicit,
        }
        if existing is not None:
            for k, v in fields.items():
                setattr(existing, k, v)
            await self.session.flush()
            return existing
        row = YandexMetadata(track_id=track_id, **fields)
        self.session.add(row)
        await self.session.flush()
        return row


class RawProviderResponseRepository(BaseRepository[RawProviderResponse]):
    model = RawProviderResponse
