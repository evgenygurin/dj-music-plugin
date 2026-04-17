"""Track features aggregate: TrackAudioFeaturesComputed + TrackSection +
TimeseriesReference + FeatureExtractionRun."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models.base import Base
from app.v2.models.track import Track
from app.v2.models.track_features import (
    FeatureExtractionRun,
    TimeseriesReference,
    TrackAudioFeaturesComputed,
    TrackSection,
)


@pytest.mark.asyncio
async def test_features_minimal(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    f = TrackAudioFeaturesComputed(track_id=t.id, bpm=128.0, key_code=5)
    session.add(f)
    await session.commit()
    loaded = await session.get(TrackAudioFeaturesComputed, t.id)
    assert loaded is not None
    assert loaded.bpm == 128.0


@pytest.mark.asyncio
async def test_features_bpm_range_constraint(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    f = TrackAudioFeaturesComputed(track_id=t.id, bpm=500.0)
    session.add(f)
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_analysis_level_constraint(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    f = TrackAudioFeaturesComputed(track_id=t.id, analysis_level=99)
    session.add(f)
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_section_type_range(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    sec = TrackSection(track_id=t.id, section_type=99, start_ms=0, end_ms=1000, energy=0.5)
    session.add(sec)
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_feature_run_status_constraint(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    run = FeatureExtractionRun(
        track_id=t.id, pipeline_name="v2", pipeline_version="1", status="bogus"
    )
    session.add(run)
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_timeseries_reference(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    ts = TimeseriesReference(
        track_id=t.id,
        feature_set="energy",
        storage_uri="cache/timeseries/1/energy.npz",
        frame_count=1200,
        hop_length=512,
        sample_rate=22050,
        dtype="float32",
        shape="[1200]",
    )
    session.add(ts)
    await session.commit()
    loaded = await session.get(TimeseriesReference, ts.id)
    assert loaded is not None
    assert loaded.frame_count == 1200
