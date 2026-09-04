"""Cell 17 — beatgrid metadata persistence tests.

Pins the contract:

* ``save_beatgrid_metadata`` writes scalar metadata + an on-disk URI
  to a single row; large arrays are NOT embedded in the relational
  row (the schema only carries a path + frame_count + hop_length).
* ``get_beatgrid_metadata`` returns the same shape on read.
* Re-saving overwrites the URI in place (idempotent upgrade path).
* The new columns are non-breaking — features rows without a
  beatgrid return ``None`` from ``get_beatgrid_metadata``.

Uses the in-memory SQLite engine from ``tests/conftest.py``; no live
Supabase required.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base, Track, TrackAudioFeaturesComputed
from app.repositories.track_features import TrackFeaturesRepository


@pytest_asyncio.fixture
async def engine() -> AsyncEngine:
    from sqlalchemy.ext.asyncio import create_async_engine

    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncSession:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s


@pytest_asyncio.fixture
async def repo(session: AsyncSession) -> TrackFeaturesRepository:
    return TrackFeaturesRepository(session)


@pytest.mark.asyncio
async def test_save_beatgrid_metadata_creates_row(
    repo: TrackFeaturesRepository, session: AsyncSession
) -> None:
    track = Track(title="t1")
    session.add(track)
    await session.flush()
    await repo.save_beatgrid_metadata(
        track.id,
        storage_uri="/cache/timeseries/1/beatgrid.npz",
        frame_count=4096,
        hop_length=512,
        sample_rate=22050,
        dominant_hypothesis_bpm=128.42,
        dominant_hypothesis_octave_preference=0.91,
    )
    meta = await repo.get_beatgrid_metadata(track.id)
    assert meta is not None
    assert meta["storage_uri"] == "/cache/timeseries/1/beatgrid.npz"
    assert meta["frame_count"] == 4096
    assert meta["hop_length"] == 512
    assert meta["sample_rate"] == 22050
    assert meta["dominant_hypothesis_bpm"] == pytest.approx(128.42)
    assert meta["dominant_hypothesis_octave_preference"] == pytest.approx(0.91)


@pytest.mark.asyncio
async def test_save_beatgrid_metadata_updates_existing_row(
    repo: TrackFeaturesRepository, session: AsyncSession
) -> None:
    track = Track(title="t1")
    session.add(track)
    await session.flush()
    # First beatgrid.
    await repo.save_beatgrid_metadata(
        track.id,
        storage_uri="/cache/v1.npz",
        frame_count=100,
        hop_length=512,
        sample_rate=22050,
    )
    # Re-analyse → new beatgrid.
    await repo.save_beatgrid_metadata(
        track.id,
        storage_uri="/cache/v2.npz",
        frame_count=200,
        hop_length=512,
        sample_rate=22050,
        dominant_hypothesis_bpm=130.0,
    )
    meta = await repo.get_beatgrid_metadata(track.id)
    assert meta is not None
    assert meta["storage_uri"] == "/cache/v2.npz"
    assert meta["frame_count"] == 200
    # Old dominant_bpm was None; new value is 130.0.
    assert meta["dominant_hypothesis_bpm"] == pytest.approx(130.0)


@pytest.mark.asyncio
async def test_get_beatgrid_metadata_returns_none_when_no_row(
    repo: TrackFeaturesRepository,
) -> None:
    meta = await repo.get_beatgrid_metadata(9999)
    assert meta is None


@pytest.mark.asyncio
async def test_get_beatgrid_metadata_returns_none_when_no_beatgrid(
    repo: TrackFeaturesRepository, session: AsyncSession
) -> None:
    """A features row exists but no beatgrid has been written."""
    track = Track(title="t1")
    session.add(track)
    await session.flush()
    session.add(
        TrackAudioFeaturesComputed(track_id=track.id, bpm=128.0, analysis_level=2)
    )
    await session.flush()
    meta = await repo.get_beatgrid_metadata(track.id)
    assert meta is None


@pytest.mark.asyncio
async def test_save_beatgrid_metadata_preserves_existing_bpm(
    repo: TrackFeaturesRepository, session: AsyncSession
) -> None:
    """A beatgrid write must NOT clobber the canonical BPM column."""
    track = Track(title="t1")
    session.add(track)
    await session.flush()
    session.add(
        TrackAudioFeaturesComputed(track_id=track.id, bpm=128.0, analysis_level=3)
    )
    await session.flush()
    await repo.save_beatgrid_metadata(
        track.id,
        storage_uri="/cache/bg.npz",
        frame_count=500,
        hop_length=512,
        sample_rate=22050,
    )
    features = (await repo.get_scoring_features_batch([track.id]))[track.id]
    assert features.bpm == 128.0
    assert features.beatgrid_arrays_ref == "/cache/bg.npz"
    assert features.beatgrid_frame_count == 500
