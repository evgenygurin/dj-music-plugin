"""Integration tests for get_candidate_pool tool."""

from __future__ import annotations

import pytest
from fastmcp import Client
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.conftest import _parse_tool_result as _parse


@pytest.mark.asyncio
async def test_candidate_pool_empty_returns_empty_list(client: Client):
    """get_candidate_pool on empty DB returns empty list."""
    result = await client.call_tool("get_candidate_pool", {})
    data = _parse(result)
    assert data["tracks"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_candidate_pool_filters_by_subgenre(client: Client, async_engine):
    """get_candidate_pool filters by subgenre (mood field)."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        from app.db.models.audio import TrackAudioFeaturesComputed
        from app.db.models.track import Track

        t1 = Track(title="Detroit Track")
        t2 = Track(title="Industrial Track")
        t3 = Track(title="Minimal Track")
        session.add_all([t1, t2, t3])
        await session.flush()
        session.add(
            TrackAudioFeaturesComputed(
                track_id=t1.id, bpm=132.0, mood="detroit", integrated_lufs=-11.5
            )
        )
        session.add(
            TrackAudioFeaturesComputed(
                track_id=t2.id, bpm=140.0, mood="industrial", integrated_lufs=-10.0
            )
        )
        session.add(
            TrackAudioFeaturesComputed(
                track_id=t3.id, bpm=128.0, mood="minimal", integrated_lufs=-12.5
            )
        )
        await session.commit()

    result = await client.call_tool("get_candidate_pool", {"subgenres": ["detroit", "industrial"]})
    data = _parse(result)
    assert data["total"] == 2
    moods = {t["mood"] for t in data["tracks"]}
    assert "detroit" in moods
    assert "industrial" in moods
    assert "minimal" not in moods


@pytest.mark.asyncio
async def test_candidate_pool_filters_by_bpm(client: Client, async_engine):
    """get_candidate_pool filters by BPM range."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        from app.db.models.audio import TrackAudioFeaturesComputed
        from app.db.models.track import Track

        for i, bpm in enumerate([126.0, 132.0, 138.0, 145.0]):
            t = Track(title=f"Track {i}")
            session.add(t)
            await session.flush()
            session.add(TrackAudioFeaturesComputed(track_id=t.id, bpm=bpm, integrated_lufs=-11.0))
        await session.commit()

    result = await client.call_tool("get_candidate_pool", {"bpm_min": 130.0, "bpm_max": 140.0})
    data = _parse(result)
    assert data["total"] == 2
    for t in data["tracks"]:
        assert 130.0 <= t["bpm"] <= 140.0


@pytest.mark.asyncio
async def test_candidate_pool_energy_level_high(client: Client, async_engine):
    """energy_level='high' filters by LUFS >= -11."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        from app.db.models.audio import TrackAudioFeaturesComputed
        from app.db.models.track import Track

        for lufs in [-14.0, -12.0, -10.5, -9.0]:
            t = Track(title=f"Track {lufs}")
            session.add(t)
            await session.flush()
            session.add(TrackAudioFeaturesComputed(track_id=t.id, bpm=132.0, integrated_lufs=lufs))
        await session.commit()

    result = await client.call_tool("get_candidate_pool", {"energy_level": "high"})
    data = _parse(result)
    assert data["total"] == 2
    for t in data["tracks"]:
        assert t["energy_lufs"] >= -11.0


@pytest.mark.asyncio
async def test_candidate_pool_respects_limit(client: Client, async_engine):
    """get_candidate_pool respects the limit parameter."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        from app.db.models.audio import TrackAudioFeaturesComputed
        from app.db.models.track import Track

        for i in range(20):
            t = Track(title=f"Track {i}")
            session.add(t)
            await session.flush()
            session.add(
                TrackAudioFeaturesComputed(track_id=t.id, bpm=132.0, integrated_lufs=-11.0)
            )
        await session.commit()

    result = await client.call_tool("get_candidate_pool", {"limit": 5})
    data = _parse(result)
    assert len(data["tracks"]) == 5
    assert data["total"] == 20
