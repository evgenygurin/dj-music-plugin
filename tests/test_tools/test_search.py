"""Tests for search and admin MCP tools."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.audio import TrackAudioFeaturesComputed
from app.models.playlist import Playlist
from app.models.set import DjSet
from app.models.track import Artist, Track, TrackExternalId

# ── Helpers ──────────────────────────────────────────


def _make_ctx():
    """Build a minimal mock Context (no longer needs session factory)."""
    ctx = MagicMock()
    ctx.enable_components = AsyncMock()
    ctx.disable_components = AsyncMock()
    return ctx


@asynccontextmanager
async def _mock_get_db_session(engine):
    """Create a mock get_db_session that uses the test engine."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
def ctx():
    """Mock MCP Context."""
    return _make_ctx()


@pytest.fixture
def patch_db_session(async_engine):
    """Patch get_db_session in all tool modules to use test engine."""

    @asynccontextmanager
    async def _test_get_db_session():
        from sqlalchemy.ext.asyncio import async_sessionmaker

        factory = async_sessionmaker(async_engine, expire_on_commit=False)
        async with factory() as session:
            yield session

    with (
        patch("app.mcp.tools.search.get_db_session", _test_get_db_session),
        patch("app.mcp.tools.admin.get_db_session", _test_get_db_session),
    ):
        yield


# ── search tool ──────────────────────────────────────


async def test_search_tracks(patch_db_session, ctx, db):
    """search() returns matching tracks grouped by entity."""
    db.add(Track(title="Amelie Lens - Exhale"))
    db.add(Track(title="999999999 - Pulse"))
    await db.flush()

    from app.mcp.tools.search import search

    result = await search(query="Lens", ctx=ctx)

    assert result["total"] >= 1
    assert any("Lens" in t["title"] for t in result["results"]["tracks"])


async def test_search_artists(patch_db_session, ctx, db):
    """search() returns matching artists."""
    db.add(Artist(name="Charlotte de Witte"))
    await db.flush()

    from app.mcp.tools.search import search

    result = await search(query="Charlotte", entity="artists", ctx=ctx)

    assert len(result["results"]["artists"]) == 1
    assert result["results"]["artists"][0]["name"] == "Charlotte de Witte"


async def test_search_playlists(patch_db_session, ctx, db):
    """search() returns matching playlists."""
    db.add(Playlist(name="Peak Time Techno"))
    await db.flush()

    from app.mcp.tools.search import search

    result = await search(query="Peak", entity="playlists", ctx=ctx)

    assert len(result["results"]["playlists"]) == 1


async def test_search_sets(patch_db_session, ctx, db):
    """search() returns matching DJ sets."""
    db.add(DjSet(name="Friday Night Set"))
    await db.flush()

    from app.mcp.tools.search import search

    result = await search(query="Friday", entity="sets", ctx=ctx)

    assert len(result["results"]["sets"]) == 1


async def test_search_empty_query(ctx):
    """search() rejects empty queries with ToolError."""
    from fastmcp.exceptions import ToolError

    from app.mcp.tools.search import search

    with pytest.raises(ToolError):
        await search(query="", ctx=ctx)


async def test_search_all_entities(patch_db_session, ctx, db):
    """search() with entity='all' queries all entity types."""
    db.add(Track(title="Test Track"))
    db.add(Artist(name="Test Artist"))
    db.add(Playlist(name="Test Playlist"))
    db.add(DjSet(name="Test Set"))
    await db.flush()

    from app.mcp.tools.search import search

    result = await search(query="Test", entity="all", ctx=ctx)

    assert "tracks" in result["results"]
    assert "artists" in result["results"]
    assert "playlists" in result["results"]
    assert "sets" in result["results"]
    assert result["total"] == 4


# ── filter_tracks tool ──────────────────────────────


async def test_filter_tracks_by_bpm(patch_db_session, ctx, db):
    """filter_tracks() filters by BPM range."""
    t1 = Track(title="Slow")
    t2 = Track(title="Fast")
    db.add_all([t1, t2])
    await db.flush()

    db.add(TrackAudioFeaturesComputed(track_id=t1.id, bpm=120.0))
    db.add(TrackAudioFeaturesComputed(track_id=t2.id, bpm=145.0))
    await db.flush()

    from app.mcp.tools.search import filter_tracks

    result = await filter_tracks(bpm_min=130.0, bpm_max=150.0, ctx=ctx)

    assert result["total"] == 1
    assert result["items"][0]["title"] == "Fast"


async def test_filter_tracks_by_key(patch_db_session, ctx, db):
    """filter_tracks() filters by exact Camelot key."""
    t1 = Track(title="Track A minor")
    db.add(t1)
    await db.flush()

    # 8A = key_code 14 (A minor)
    db.add(TrackAudioFeaturesComputed(track_id=t1.id, bpm=130.0, key_code=14))
    await db.flush()

    from app.mcp.tools.search import filter_tracks

    result = await filter_tracks(key="8A", ctx=ctx)

    assert result["total"] == 1
    assert result["items"][0]["title"] == "Track A minor"


async def test_filter_tracks_by_key_compatible(patch_db_session, ctx, db):
    """filter_tracks() with key_compatible returns harmonically compatible tracks."""
    t1 = Track(title="Track 8A")
    t2 = Track(title="Track 9A")
    t3 = Track(title="Track 3B")
    db.add_all([t1, t2, t3])
    await db.flush()

    # 8A=14, 9A=16, 3B=5
    db.add(TrackAudioFeaturesComputed(track_id=t1.id, bpm=130.0, key_code=14))
    db.add(TrackAudioFeaturesComputed(track_id=t2.id, bpm=132.0, key_code=16))
    db.add(TrackAudioFeaturesComputed(track_id=t3.id, bpm=128.0, key_code=5))
    await db.flush()

    from app.mcp.tools.search import filter_tracks

    # Compatible with 8A (14): 7A(12), 8A(14), 9A(16), 8B(15) -> distance <= 1
    result = await filter_tracks(key_compatible="8A", ctx=ctx)

    titles = {item["title"] for item in result["items"]}
    assert "Track 8A" in titles
    assert "Track 9A" in titles
    assert "Track 3B" not in titles


async def test_filter_tracks_by_energy(patch_db_session, ctx, db):
    """filter_tracks() filters by energy range."""
    t1 = Track(title="Chill")
    t2 = Track(title="Intense")
    db.add_all([t1, t2])
    await db.flush()

    db.add(TrackAudioFeaturesComputed(track_id=t1.id, bpm=120.0, energy_mean=0.3))
    db.add(TrackAudioFeaturesComputed(track_id=t2.id, bpm=140.0, energy_mean=0.9))
    await db.flush()

    from app.mcp.tools.search import filter_tracks

    result = await filter_tracks(energy_min=0.7, ctx=ctx)

    assert result["total"] == 1
    assert result["items"][0]["title"] == "Intense"


async def test_filter_tracks_invalid_key(patch_db_session, ctx):
    """filter_tracks() raises ToolError for invalid Camelot key."""
    from fastmcp.exceptions import ToolError

    from app.mcp.tools.search import filter_tracks

    with pytest.raises(ToolError):
        await filter_tracks(key="ZZ", ctx=ctx)


# ── unlock_tools tool ────────────────────────────────


async def test_unlock_tools_unlock(ctx):
    """unlock_tools() calls enable_components with correct tags."""
    from app.mcp.tools.admin import unlock_tools

    result = await unlock_tools(action="unlock", category="audio", ctx=ctx)

    assert result["action"] == "unlocked"
    assert "audio" in result["categories"]
    ctx.enable_components.assert_awaited_once_with(tags={"audio"})


async def test_unlock_tools_lock(ctx):
    """unlock_tools() calls disable_components with correct tags."""
    from app.mcp.tools.admin import unlock_tools

    result = await unlock_tools(action="lock", category="discovery", ctx=ctx)

    assert result["action"] == "locked"
    assert "discovery" in result["categories"]
    ctx.disable_components.assert_awaited_once_with(tags={"discovery"})


async def test_unlock_tools_unlock_all(ctx):
    """unlock_tools() with category='all' unlocks all extended categories."""
    from app.mcp.tools.admin import unlock_tools

    result = await unlock_tools(action="unlock", category="all", ctx=ctx)

    assert result["action"] == "unlocked"
    assert len(result["categories"]) == 6


async def test_unlock_tools_status(ctx):
    """unlock_tools() with action='status' returns status message."""
    from app.mcp.tools.admin import unlock_tools

    result = await unlock_tools(action="status", ctx=ctx)

    assert result["action"] == "status"


async def test_unlock_tools_invalid_category(ctx):
    """unlock_tools() raises ToolError for unknown categories."""
    from fastmcp.exceptions import ToolError

    from app.mcp.tools.admin import unlock_tools

    with pytest.raises(ToolError):
        await unlock_tools(action="unlock", category="nonexistent", ctx=ctx)


# ── list_platforms tool ──────────────────────────────


async def test_list_platforms(patch_db_session, ctx, db):
    """list_platforms() returns all providers with linked counts."""
    t1 = Track(title="Test")
    db.add(t1)
    await db.flush()

    db.add(TrackExternalId(track_id=t1.id, platform="yandex_music", external_id="123"))
    await db.flush()

    from app.mcp.tools.admin import list_platforms

    result = await list_platforms(ctx=ctx)

    assert isinstance(result, list)
    assert len(result) == 4  # 4 providers in Provider enum
    ym = next(p for p in result if p["platform"] == "yandex_music")
    assert ym["linked_tracks"] == 1
    assert ym["available"] is True


async def test_list_platforms_empty(patch_db_session, ctx, db):
    """list_platforms() returns zeros when no tracks are linked."""
    from app.mcp.tools.admin import list_platforms

    result = await list_platforms(ctx=ctx)

    assert all(p["linked_tracks"] == 0 for p in result)
