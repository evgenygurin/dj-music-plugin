"""Seed is idempotent and populates all 24 keys + 4 providers."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.db.seed import seed_reference
from app.v2.models import Base, Key, Provider


@pytest.mark.asyncio
async def test_seed_populates_keys_and_providers(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_reference(session)
    await session.commit()

    key_count = await session.scalar(select(func.count()).select_from(Key))
    prov_count = await session.scalar(select(func.count()).select_from(Provider))
    assert key_count == 24
    assert prov_count == 4


@pytest.mark.asyncio
async def test_seed_is_idempotent(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_reference(session)
    await session.commit()
    await seed_reference(session)
    await session.commit()

    key_count = await session.scalar(select(func.count()).select_from(Key))
    prov_count = await session.scalar(select(func.count()).select_from(Provider))
    assert key_count == 24
    assert prov_count == 4
