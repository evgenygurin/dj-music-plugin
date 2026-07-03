"""Aggregate type gate — boolean columns must be rejected up front.

Live probe 2026-07-03: ``entity_aggregate(track_features, sum,
variable_tempo)`` and ``(..., min_max, variable_tempo)`` both leaked a
masked "database programming error" from Postgres (``sum(boolean)`` /
``min(boolean)`` don't exist there). Two holes in the audit-iter-4 gate:

1. ``bool`` is a subclass of ``int`` in Python, so a Boolean column
   passed the ``issubclass(py_type, (int, float, Decimal))`` check for
   sum/avg and died in SQL instead of raising a typed error.
2. ``min_max`` was not gated at all. min/max over strings and dates is
   valid SQL (kept allowed); only booleans lack the aggregate.

SQLite (tests) happily sums booleans as 0/1, so these tests pin the
GATE (raised before any SQL), not the SQL failure.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base
from app.models.track import Track
from app.models.track_features import TrackAudioFeaturesComputed
from app.repositories.track import TrackRepository
from app.repositories.track_features import TrackFeaturesRepository
from app.shared.errors import ValidationError

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def _tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _seed(session: AsyncSession) -> None:
    track = Track(title="Gated")
    session.add(track)
    await session.flush()
    session.add(
        TrackAudioFeaturesComputed(
            track_id=track.id, analysis_level=2, bpm=128.0, variable_tempo=False
        )
    )
    await session.flush()


@pytest.mark.parametrize("op", ["sum", "avg", "min_max"])
async def test_bool_column_rejected_with_typed_error(session: AsyncSession, op: str) -> None:
    await _seed(session)
    repo = TrackFeaturesRepository(session)
    with pytest.raises(ValidationError, match="variable_tempo"):
        await repo.aggregate(operation=op, field="variable_tempo")


async def test_min_max_on_string_still_allowed(session: AsyncSession) -> None:
    """min/max over a string column is valid SQL — must NOT be gated."""
    await _seed(session)
    repo = TrackRepository(session)
    result = await repo.aggregate(operation="min_max", field="title")
    assert result == {"min": "Gated", "max": "Gated"}


async def test_min_max_on_numeric_still_allowed(session: AsyncSession) -> None:
    await _seed(session)
    repo = TrackFeaturesRepository(session)
    result = await repo.aggregate(operation="min_max", field="bpm")
    assert result == {"min": 128.0, "max": 128.0}
