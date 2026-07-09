from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.track_features import TrackSection
from app.repositories.track_section import TrackSectionRepository

_TRACK_SECTIONS_DDL = text(
    """
    CREATE TABLE IF NOT EXISTS track_sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        track_id INTEGER NOT NULL,
        section_type INTEGER NOT NULL,
        start_ms INTEGER NOT NULL,
        end_ms INTEGER NOT NULL,
        energy REAL,
        confidence REAL,
        lufs REAL,
        spectral_centroid REAL,
        stem_energy TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
        CHECK(section_type BETWEEN 0 AND 11)
    )
    """
)


@pytest_asyncio.fixture
async def repo(engine: AsyncEngine, session: AsyncSession) -> TrackSectionRepository:
    async with engine.begin() as conn:
        await conn.execute(_TRACK_SECTIONS_DDL)
    return TrackSectionRepository(session)


@pytest.mark.asyncio
async def test_get_by_id(repo: TrackSectionRepository, session: AsyncSession):
    row = TrackSection(track_id=1, section_type=3, start_ms=0, end_ms=32000)
    session.add(row)
    await session.flush()

    fetched = await repo.get(row.id)
    assert fetched is not None
    assert fetched.track_id == 1


@pytest.mark.asyncio
async def test_get_missing_returns_none(repo: TrackSectionRepository):
    assert await repo.get(99999) is None


@pytest.mark.asyncio
async def test_filter_by_track(repo: TrackSectionRepository, session: AsyncSession):
    s1 = TrackSection(track_id=1, section_type=1, start_ms=0, end_ms=16000)
    s2 = TrackSection(track_id=1, section_type=2, start_ms=16000, end_ms=32000)
    session.add_all([s1, s2])
    await session.flush()

    result = await repo.filter(where={"track_id__eq": 1})
    rows = result.items
    assert len(rows) == 2
