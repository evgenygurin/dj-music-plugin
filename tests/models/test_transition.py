"""Transition (persisted scored pair) + TransitionHistory (run log)."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.base import Base
from app.models.track import Track
from app.models.transition import Transition
from app.models.transition_history import TransitionHistory


@pytest.mark.asyncio
async def test_transition_score_bounds(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([t1, t2])
    await session.flush()
    tr = Transition(from_track_id=t1.id, to_track_id=t2.id, overall_quality=2.0)
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
        bpm_score=0.5,
        energy_score=1.0,
        harmonic_score=0.7,
        spectral_score=0.6,
        groove_score=0.8,
        timbral_score=0.65,
        key_distance_weighted=0.1,
        overall_quality=0.75,
        fx_type="bass_swap_short",
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
        user_reaction=None,
    )
    session.add(h)
    await session.commit()
    assert h.id is not None
