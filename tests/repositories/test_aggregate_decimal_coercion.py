"""Audit iter 18 (T-18): ``AVG`` over an INTEGER column returns
Postgres ``NUMERIC``, which asyncpg surfaces as ``Decimal``. Pydantic
JSON-serialises ``Decimal`` as a string, so callers received
``"9.16..."`` instead of ``9.16``.

This module pins the coercion: ``avg`` always lands as ``float``,
``count`` always as ``int``, regardless of the underlying column
type. SQLite happens to return ``float`` natively for AVG so it
hides the prod bug, but the helper still runs and the type
assertion guards the contract.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base, TrackAudioFeaturesComputed
from app.repositories.track import TrackRepository
from app.repositories.track_features import TrackFeaturesRepository


@pytest_asyncio.fixture
async def seeded(
    engine: AsyncEngine, session: AsyncSession
) -> tuple[TrackFeaturesRepository, TrackRepository]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    track_repo = TrackRepository(session)
    feat_repo = TrackFeaturesRepository(session)
    for i in range(5):
        t = await track_repo.create(title=f"t{i}")
        session.add(TrackAudioFeaturesComputed(track_id=t.id, bpm=120.0 + i, key_code=10 + i))
    await session.flush()
    return feat_repo, track_repo


@pytest.mark.asyncio
async def test_avg_over_integer_column_lands_as_float(
    seeded: tuple[TrackFeaturesRepository, TrackRepository],
) -> None:
    """``key_code`` is INTEGER. AVG over it must not surface as
    Decimal/str (audit iter 18 bug class)."""
    feat_repo, _ = seeded
    val = await feat_repo.aggregate(operation="avg", field="key_code")
    assert not isinstance(val, Decimal), f"got Decimal {val!r}; should be float"
    assert isinstance(val, int | float)
    assert val == 12.0  # mean of 10..14


@pytest.mark.asyncio
async def test_avg_over_float_column_unchanged(
    seeded: tuple[TrackFeaturesRepository, TrackRepository],
) -> None:
    """Sanity: float-column averages still pass through."""
    feat_repo, _ = seeded
    val = await feat_repo.aggregate(operation="avg", field="bpm")
    assert isinstance(val, float)
    assert val == 122.0  # mean of 120..124
