"""Audit iter 4: ``entity_aggregate(... operation='avg', field='title')``
on a string column leaked the raw asyncpg ``function avg(character
varying) does not exist`` SQL error to the MCP client.

Type validation should run at the dispatcher / repository layer
before the SQL query is issued, producing a clean ``ValidationError``
with a useful message instead of a backend stack trace.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base
from app.repositories.track import TrackRepository
from app.shared.errors import ValidationError


@pytest_asyncio.fixture
async def repo(engine: AsyncEngine, session: AsyncSession) -> TrackRepository:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    repo = TrackRepository(session)
    await repo.create(title="x")
    await repo.create(title="y")
    return repo


@pytest.mark.asyncio
async def test_avg_on_string_column_raises_typed_error(repo: TrackRepository) -> None:
    with pytest.raises(ValidationError, match=r"(?i)numeric"):
        await repo.aggregate(operation="avg", field="title")


@pytest.mark.asyncio
async def test_sum_on_string_column_raises_typed_error(repo: TrackRepository) -> None:
    with pytest.raises(ValidationError, match=r"(?i)numeric"):
        await repo.aggregate(operation="sum", field="title")


@pytest.mark.asyncio
async def test_avg_on_numeric_column_still_works(repo: TrackRepository) -> None:
    """Sanity: numeric ops still succeed on numeric columns."""
    val = await repo.aggregate(operation="avg", field="duration_ms")
    assert val == 0  # both rows have duration_ms=NULL, coalesced to 0


@pytest.mark.asyncio
async def test_count_does_not_require_field(repo: TrackRepository) -> None:
    """Sanity: ``count`` skips the type check."""
    val = await repo.aggregate(operation="count")
    assert val == 2


@pytest.mark.asyncio
async def test_distinct_on_string_still_works(repo: TrackRepository) -> None:
    """Sanity: ``distinct`` accepts any column type."""
    titles = await repo.aggregate(operation="distinct", field="title")
    assert sorted(titles) == ["x", "y"]


@pytest.mark.asyncio
async def test_min_max_on_string_still_works(repo: TrackRepository) -> None:
    """Sanity: SQL min/max on strings is lexicographic and meaningful."""
    bounds = await repo.aggregate(operation="min_max", field="title")
    assert bounds == {"min": "x", "max": "y"}
