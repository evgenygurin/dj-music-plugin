"""Reference model tests: keys + key_edges."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models.base import Base
from app.v2.models.key import Key, KeyEdge


@pytest.mark.asyncio
async def test_create_key(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session.add(Key(key_code=0, pitch_class=0, mode=0, name="C minor", camelot="5A"))
    await session.commit()
    k = await session.get(Key, 0)
    assert k is not None
    assert k.camelot == "5A"
    assert k.mode == 0


@pytest.mark.asyncio
async def test_key_code_range(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session.add(Key(key_code=99, pitch_class=0, mode=0, name="bad", camelot="xx"))
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_key_edge_distance_range(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session.add(KeyEdge(from_key=0, to_key=1, distance=99, weight=1.0, rule_name="bad"))
    with pytest.raises(IntegrityError):
        await session.commit()
