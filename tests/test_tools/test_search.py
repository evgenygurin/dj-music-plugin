"""Tests for search and admin MCP tools via FastMCP Client."""

from __future__ import annotations

import pytest
from fastmcp import Client

from tests.conftest import _parse_tool_result as _parse_result

# ── search tool ──────────────────────────────────────


async def test_search_tracks(client: Client, async_engine):
    """search() returns matching tracks grouped by entity."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        session.add(Track(title="Amelie Lens - Exhale"))
        session.add(Track(title="999999999 - Pulse"))
        await session.commit()

    result = await client.call_tool("search", {"query": "Lens"})
    data = _parse_result(result)

    assert data["total"] >= 1
    assert any("Lens" in t["title"] for t in data["results"]["tracks"])


async def test_search_artists(client: Client, async_engine):
    """search() returns matching artists."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.track import Artist

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        session.add(Artist(name="Charlotte de Witte"))
        await session.commit()

    result = await client.call_tool("search", {"query": "Charlotte", "entity": "artists"})
    data = _parse_result(result)

    assert len(data["results"]["artists"]) == 1
    assert data["results"]["artists"][0]["name"] == "Charlotte de Witte"


async def test_search_playlists(client: Client, async_engine):
    """search() returns matching playlists."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.playlist import Playlist

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        session.add(Playlist(name="Peak Time Techno"))
        await session.commit()

    result = await client.call_tool("search", {"query": "Peak", "entity": "playlists"})
    data = _parse_result(result)

    assert len(data["results"]["playlists"]) == 1


async def test_search_sets(client: Client, async_engine):
    """search() returns matching DJ sets."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.set import DjSet

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        session.add(DjSet(name="Friday Night Set"))
        await session.commit()

    result = await client.call_tool("search", {"query": "Friday", "entity": "sets"})
    data = _parse_result(result)

    assert len(data["results"]["sets"]) == 1


async def test_search_empty_query(client: Client):
    """search() rejects empty queries with ToolError."""
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await client.call_tool("search", {"query": ""})


async def test_search_all_entities(client: Client, async_engine):
    """search() with entity='all' queries all entity types."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.playlist import Playlist
    from app.db.models.set import DjSet
    from app.db.models.track import Artist, Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        session.add(Track(title="Test Track"))
        session.add(Artist(name="Test Artist"))
        session.add(Playlist(name="Test Playlist"))
        session.add(DjSet(name="Test Set"))
        await session.commit()

    result = await client.call_tool("search", {"query": "Test", "entity": "all"})
    data = _parse_result(result)

    assert "tracks" in data["results"]
    assert "artists" in data["results"]
    assert "playlists" in data["results"]
    assert "sets" in data["results"]
    assert data["total"] == 4


# ── filter_tracks tool ──────────────────────────────


async def test_filter_tracks_by_bpm(client: Client, async_engine):
    """filter_tracks() filters by BPM range."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.audio import TrackAudioFeaturesComputed
    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        t1 = Track(title="Slow")
        t2 = Track(title="Fast")
        session.add_all([t1, t2])
        await session.flush()
        session.add(TrackAudioFeaturesComputed(track_id=t1.id, bpm=120.0))
        session.add(TrackAudioFeaturesComputed(track_id=t2.id, bpm=145.0))
        await session.commit()

    result = await client.call_tool("filter_tracks", {"bpm_min": 130.0, "bpm_max": 150.0})
    data = _parse_result(result)

    assert data["total"] == 1
    assert data["items"][0]["title"] == "Fast"


async def test_filter_tracks_by_key(client: Client, async_engine):
    """filter_tracks() filters by exact Camelot key."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.audio import TrackAudioFeaturesComputed
    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        t1 = Track(title="Track A minor")
        session.add(t1)
        await session.flush()
        # 8A = key_code 14 (A minor)
        session.add(TrackAudioFeaturesComputed(track_id=t1.id, bpm=130.0, key_code=14))
        await session.commit()

    result = await client.call_tool("filter_tracks", {"key": "8A"})
    data = _parse_result(result)

    assert data["total"] == 1
    assert data["items"][0]["title"] == "Track A minor"


async def test_filter_tracks_by_key_compatible(client: Client, async_engine):
    """filter_tracks() with key_compatible returns harmonically compatible tracks."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.audio import TrackAudioFeaturesComputed
    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        t1 = Track(title="Track 8A")
        t2 = Track(title="Track 9A")
        t3 = Track(title="Track 3B")
        session.add_all([t1, t2, t3])
        await session.flush()
        # 8A=14, 9A=16, 3B=5
        session.add(TrackAudioFeaturesComputed(track_id=t1.id, bpm=130.0, key_code=14))
        session.add(TrackAudioFeaturesComputed(track_id=t2.id, bpm=132.0, key_code=16))
        session.add(TrackAudioFeaturesComputed(track_id=t3.id, bpm=128.0, key_code=5))
        await session.commit()

    # Compatible with 8A (14): 7A(12), 8A(14), 9A(16), 8B(15) -> distance <= 1
    result = await client.call_tool("filter_tracks", {"key_compatible": "8A"})
    data = _parse_result(result)

    titles = {item["title"] for item in data["items"]}
    assert "Track 8A" in titles
    assert "Track 9A" in titles
    assert "Track 3B" not in titles


async def test_filter_tracks_by_energy(client: Client, async_engine):
    """filter_tracks() filters by energy range."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.audio import TrackAudioFeaturesComputed
    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        t1 = Track(title="Chill")
        t2 = Track(title="Intense")
        session.add_all([t1, t2])
        await session.flush()
        session.add(TrackAudioFeaturesComputed(track_id=t1.id, bpm=120.0, energy_mean=0.3))
        session.add(TrackAudioFeaturesComputed(track_id=t2.id, bpm=140.0, energy_mean=0.9))
        await session.commit()

    result = await client.call_tool("filter_tracks", {"energy_min": 0.7})
    data = _parse_result(result)

    assert data["total"] == 1
    assert data["items"][0]["title"] == "Intense"


async def test_filter_tracks_invalid_key(client: Client):
    """filter_tracks() raises ToolError for invalid Camelot key."""
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await client.call_tool("filter_tracks", {"key": "ZZ"})


# ── unlock_tools tool ────────────────────────────────


async def test_unlock_tools_unlock(client: Client):
    """unlock_tools() unlocks the given category."""
    result = await client.call_tool("unlock_tools", {"action": "unlock", "category": "audio"})
    data = _parse_result(result)

    assert data["action"] == "unlocked"
    assert "audio" in data["categories"]


async def test_unlock_tools_lock(client: Client):
    """unlock_tools() locks the given category."""
    result = await client.call_tool("unlock_tools", {"action": "lock", "category": "discovery"})
    data = _parse_result(result)

    assert data["action"] == "locked"
    assert "discovery" in data["categories"]


async def test_unlock_tools_unlock_all(client: Client):
    """unlock_tools() with category='all' unlocks all extended categories."""
    result = await client.call_tool("unlock_tools", {"action": "unlock", "category": "all"})
    data = _parse_result(result)

    assert data["action"] == "unlocked"
    assert len(data["categories"]) == 7  # +atomic


async def test_unlock_tools_status(client: Client):
    """unlock_tools() with action='status' reports effective per-category state."""
    result = await client.call_tool("unlock_tools", {"action": "status"})
    data = _parse_result(result)

    assert data["action"] == "status"
    assert "toggleable_categories" in data
    assert "effective" in data
    assert "session_rules" in data
    # All toggleable categories must appear in the effective map.
    assert set(data["effective"].keys()) == set(data["toggleable_categories"])
    # Default state when no rules have run.
    assert all(state == "default" for state in data["effective"].values())


async def test_unlock_tools_status_after_unlock_reflects_state(client: Client):
    """After unlocking a category, status should report it as enabled."""
    await client.call_tool("unlock_tools", {"action": "unlock", "category": "audio"})

    result = await client.call_tool("unlock_tools", {"action": "status"})
    data = _parse_result(result)

    assert data["effective"]["audio"] == "enabled"


async def test_unlock_tools_invalid_category(client: Client):
    """unlock_tools() raises ToolError for unknown categories."""
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await client.call_tool("unlock_tools", {"action": "unlock", "category": "nonexistent"})


# ── list_platforms tool ──────────────────────────────


async def test_list_platforms(client: Client, async_engine):
    """list_platforms() returns all providers with linked counts."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.track import Track, TrackExternalId

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        t1 = Track(title="Test")
        session.add(t1)
        await session.flush()
        session.add(TrackExternalId(track_id=t1.id, platform="yandex_music", external_id="123"))
        await session.commit()

    result = await client.call_tool("list_platforms", {})
    data = _parse_result(result)

    assert isinstance(data, list)
    assert len(data) == 4  # 4 providers in Provider enum
    ym = next(p for p in data if p["platform"] == "yandex_music")
    assert ym["linked_tracks"] == 1
    assert ym["available"] is True


async def test_list_platforms_empty(client: Client):
    """list_platforms() returns zeros when no tracks are linked."""
    result = await client.call_tool("list_platforms", {})
    data = _parse_result(result)

    assert all(p["linked_tracks"] == 0 for p in data)
