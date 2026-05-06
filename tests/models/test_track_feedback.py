"""TrackFeedback (status / rating / play_count / skip_count) — synced 2026-05-07."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.base import Base
from app.models.track import Track
from app.models.track_feedback import TrackFeedback


@pytest.mark.asyncio
async def test_feedback_minimal(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    fb = TrackFeedback(track_id=t.id, status="liked")
    session.add(fb)
    await session.commit()
    assert fb.id is not None
    assert fb.rating == 3
    assert fb.play_count == 0


@pytest.mark.asyncio
async def test_feedback_status_constraint(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    fb = TrackFeedback(track_id=t.id, status="bogus")
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
    fb = TrackFeedback(track_id=t.id, status="liked", rating=99)
    session.add(fb)
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_feedback_unique_per_track(engine: AsyncEngine, session: AsyncSession) -> None:
    """Prod schema enforces UNIQUE(track_id) — only one feedback row per track."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    session.add(TrackFeedback(track_id=t.id, status="liked"))
    await session.commit()
    session.add(TrackFeedback(track_id=t.id, status="banned"))
    with pytest.raises(IntegrityError):
        await session.commit()
