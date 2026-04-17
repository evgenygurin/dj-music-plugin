"""TrackFeaturesRepository domain methods."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models import Base, Track, TrackAudioFeaturesComputed
from app.v2.repositories.track_features import TrackFeaturesRepository


@pytest_asyncio.fixture
async def repo(engine: AsyncEngine, session: AsyncSession) -> TrackFeaturesRepository:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return TrackFeaturesRepository(session)


@pytest.mark.asyncio
async def test_get_scoring_features_batch(
    repo: TrackFeaturesRepository, session: AsyncSession
) -> None:
    t1, t2, t3 = Track(title="a"), Track(title="b"), Track(title="c")
    session.add_all([t1, t2, t3])
    await session.flush()
    session.add_all(
        [
            TrackAudioFeaturesComputed(track_id=t1.id, bpm=128.0, analysis_level=3),
            TrackAudioFeaturesComputed(track_id=t2.id, bpm=130.0, analysis_level=3),
        ]
    )
    await session.flush()
    result = await repo.get_scoring_features_batch([t1.id, t2.id, t3.id])
    assert set(result.keys()) == {t1.id, t2.id}
    assert result[t1.id].bpm == 128.0


@pytest.mark.asyncio
async def test_set_mood(repo: TrackFeaturesRepository, session: AsyncSession) -> None:
    t = Track(title="a")
    session.add(t)
    await session.flush()
    session.add(TrackAudioFeaturesComputed(track_id=t.id, bpm=128.0))
    await session.flush()
    await repo.set_mood(t.id, mood="peak_time", confidence=0.82)
    row = await session.get(TrackAudioFeaturesComputed, t.id)
    assert row is not None
    assert row.mood == "peak_time"
    assert row.mood_confidence == 0.82
