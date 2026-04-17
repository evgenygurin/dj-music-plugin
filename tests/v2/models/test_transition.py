"""Transition (persisted scored pair) + TransitionHistory (run log)."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models.base import Base
from app.v2.models.track import Track
from app.v2.models.transition import Transition
from app.v2.models.transition_history import TransitionHistory


@pytest.mark.asyncio
async def test_transition_score_bounds(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([t1, t2])
    await session.flush()
    tr = Transition(from_track_id=t1.id, to_track_id=t2.id, overall_score=2.0)
    session.add(tr)
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_transition_happy_path(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([t1, t2])
    await session.flush()
    tr = Transition(
        from_track_id=t1.id,
        to_track_id=t2.id,
        bpm_distance=0.5,
        energy_step=1.0,
        groove_similarity=0.8,
        key_distance_weighted=0.1,
        overall_quality=0.75,
        overall_score=0.75,
    )
    session.add(tr)
    await session.commit()
    assert tr.id is not None


@pytest.mark.asyncio
async def test_transition_history_log(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([t1, t2])
    await session.flush()
    h = TransitionHistory(
        from_track_id=t1.id,
        to_track_id=t2.id,
        overall_score=0.78,
        style="bass_swap_short",
        reaction=None,
    )
    session.add(h)
    await session.commit()
    assert h.id is not None
