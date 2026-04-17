"""TrackFeedback (like/ban/rate + notes)."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models.base import Base
from app.v2.models.track import Track
from app.v2.models.track_feedback import TrackFeedback


@pytest.mark.asyncio
async def test_feedback_minimal(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    fb = TrackFeedback(track_id=t.id, kind="like")
    session.add(fb)
    await session.commit()
    assert fb.id is not None


@pytest.mark.asyncio
async def test_feedback_kind_constraint(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    fb = TrackFeedback(track_id=t.id, kind="bogus")
    session.add(fb)
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_feedback_rating_range(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    fb = TrackFeedback(track_id=t.id, kind="rate", rating=99)
    session.add(fb)
    with pytest.raises(IntegrityError):
        await session.commit()
