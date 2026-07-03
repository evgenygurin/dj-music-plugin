"""DB-level backstop: track_affinity forbids self-pairs.

The pydantic gate on ``TrackAffinityCreate`` (audit iter 54) rejects
``track_a_id == track_b_id`` at the tool boundary, but a raw insert
(migration, script, direct SQL) bypassed it — and one such degenerate
row (id=1, 146↔146) existed in prod from before the gate landed (probe
2026-07-03). ``ck_affinity_distinct_pair`` is the DB-level backstop.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base
from app.models.track import Track
from app.models.track_affinity import TrackAffinity

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def test_self_pair_insert_rejected_by_db(session: AsyncSession) -> None:
    track = Track(title="Solo")
    session.add(track)
    await session.flush()

    session.add(TrackAffinity(track_a_id=track.id, track_b_id=track.id))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_distinct_pair_insert_allowed(session: AsyncSession) -> None:
    a, b = Track(title="A"), Track(title="B")
    session.add_all([a, b])
    await session.flush()

    session.add(TrackAffinity(track_a_id=a.id, track_b_id=b.id))
    await session.flush()  # must not raise
