"""TrackAffinity (aggregated pair stats from history) — synced 2026-05-07."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.base import Base
from app.models.track import Track
from app.models.track_affinity import TrackAffinity


@pytest.mark.asyncio
async def test_affinity_pair(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([t1, t2])
    await session.flush()
    a = TrackAffinity(
        track_a_id=t1.id,
        track_b_id=t2.id,
        play_count=3,
        like_count=2,
        ban_count=0,
        skip_count=1,
        net_sentiment=0.5,
        avg_score=0.82,
    )
    session.add(a)
    await session.commit()
    assert a.id is not None
    assert a.like_count == 2
    assert a.net_sentiment == 0.5
