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
    session.add(Provider(name="yandex_music"))
    await session.commit()
    provs = (await session.execute(select(Provider))).scalars().all()
    assert len(provs) == 1
    assert provs[0].name == "yandex_music"


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
    ym = (
        await session.execute(select(YandexMetadata).where(YandexMetadata.track_id == 1))
    ).scalar_one()
    assert ym.yandex_track_id == "12345"


@pytest.mark.asyncio
async def test_yandex_metadata_track_id_unique(engine: AsyncEngine, session: AsyncSession) -> None:
    """``track_id`` is UNIQUE in prod — second insert for same track must raise."""
    from sqlalchemy.exc import IntegrityError

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session.add(Track(id=1, title="t"))
    await session.commit()
    session.add(YandexMetadata(track_id=1, yandex_track_id="12345"))
    await session.commit()
    session.add(YandexMetadata(track_id=1, yandex_track_id="67890"))
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_raw_response_persists_provider_link(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session.add(Track(id=1, title="t"))
    session.add(Provider(id=1, name="yandex_music"))
    await session.commit()
    session.add(
        RawProviderResponse(
            track_id=1,
            provider_id=1,
            raw_data='{"id":"12345"}',
        )
    )
    await session.commit()
    rows = (await session.execute(select(RawProviderResponse))).scalars().all()
    assert len(rows) == 1
    assert rows[0].provider_id == 1
    assert rows[0].raw_data is not None
    assert rows[0].raw_data.startswith("{")
