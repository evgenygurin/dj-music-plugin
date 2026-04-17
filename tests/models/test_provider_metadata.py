"""Provider + YandexMetadata + RawProviderResponse."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.base import Base
from app.models.provider_metadata import (
    Provider,
    RawProviderResponse,
    YandexMetadata,
)
from app.models.track import Track


@pytest.mark.asyncio
async def test_provider_row(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session.add(Provider(code="yandex_music", display_name="Yandex Music"))
    await session.commit()
    provs = (await session.execute(select(Provider))).scalars().all()
    assert len(provs) == 1
    assert provs[0].code == "yandex_music"


@pytest.mark.asyncio
async def test_yandex_metadata_requires_track(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session.add(Track(id=1, title="t"))
    await session.commit()
    session.add(
        YandexMetadata(track_id=1, yandex_track_id="12345", album_id=None, duration_ms=180000)
    )
    await session.commit()
    ym = await session.get(YandexMetadata, 1)
    assert ym is not None
    assert ym.yandex_track_id == "12345"


@pytest.mark.asyncio
async def test_raw_response_body(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session.add(Track(id=1, title="t"))
    await session.commit()
    session.add(
        RawProviderResponse(
            track_id=1,
            provider_code="yandex_music",
            endpoint="/tracks/12345",
            body='{"id":"12345"}',
        )
    )
    await session.commit()
    rows = (await session.execute(select(RawProviderResponse))).scalars().all()
    assert len(rows) == 1
    assert rows[0].body.startswith("{")
