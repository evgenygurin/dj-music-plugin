"""Tests for CRUD MCP tools via FastMCP Client."""

from __future__ import annotations

import pytest
from fastmcp import Client

from tests.conftest import _parse_tool_result as _parse_result

# ── list_tracks ──────────────────────────────────────


async def test_list_tracks_empty(client: Client):
    """list_tracks on empty db returns empty items."""
    result = await client.call_tool("list_tracks", {})
    data = _parse_result(result)
    assert data["items"] == []
    assert data["total"] == 0
    assert data["next_cursor"] is None


async def test_list_tracks_with_data(client: Client, async_engine):
    """list_tracks returns paginated tracks after seeding data."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        for i in range(5):
            session.add(Track(title=f"Track {i}"))
        await session.commit()

    result = await client.call_tool("list_tracks", {"limit": 3})
    data = _parse_result(result)
    assert len(data["items"]) == 3
    assert data["total"] == 5
    assert data["next_cursor"] is not None


# ── get_track ────────────────────────────────────────


async def test_get_track_by_id(client: Client, async_engine):
    """get_track returns track details by id."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        track = Track(title="Test Track Alpha")
        session.add(track)
        await session.flush()
        track_id = track.id
        await session.commit()

    result = await client.call_tool("get_track", {"id": track_id})
    data = _parse_result(result)
    assert data["id"] == track_id
    assert data["title"] == "Test Track Alpha"


async def test_get_track_by_query(client: Client, async_engine):
    """get_track finds track by text query."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        session.add(Track(title="Aphex Twin - Xtal"))
        await session.commit()

    result = await client.call_tool("get_track", {"query": "Aphex"})
    data = _parse_result(result)
    assert "Aphex" in data["title"]


async def test_get_track_not_found(client: Client):
    """get_track raises ToolError when not found."""
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await client.call_tool("get_track", {"id": 999})


# ── manage_tracks ────────────────────────────────────


async def test_manage_tracks_create(client: Client):
    """manage_tracks create action creates a new track."""
    result = await client.call_tool(
        "manage_tracks",
        {"action": "create", "data": {"title": "New Track", "duration_ms": 300000}},
    )
    data = _parse_result(result)
    assert data["title"] == "New Track"
    assert data["duration_ms"] == 300000
    assert data["status"] == 0
    assert "id" in data


async def test_manage_tracks_archive(client: Client, async_engine):
    """manage_tracks archive sets status to 1."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        track = Track(title="To Archive")
        session.add(track)
        await session.flush()
        track_id = track.id
        await session.commit()

    result = await client.call_tool(
        "manage_tracks",
        {"action": "archive", "data": {"id": track_id}},
    )
    data = _parse_result(result)
    assert data["status"] == 1


async def test_manage_tracks_update(client: Client, async_engine):
    """manage_tracks update modifies track fields."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        track = Track(title="Old Title")
        session.add(track)
        await session.flush()
        track_id = track.id
        await session.commit()

    result = await client.call_tool(
        "manage_tracks",
        {"action": "update", "data": {"id": track_id, "title": "New Title"}},
    )
    data = _parse_result(result)
    assert data["title"] == "New Title"


async def test_manage_tracks_invalid_action(client: Client):
    """manage_tracks rejects invalid action with ToolError."""
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await client.call_tool("manage_tracks", {"action": "explode"})


# ── list_playlists ───────────────────────────────────


async def test_list_playlists_empty(client: Client):
    """list_playlists on empty db returns no items."""
    result = await client.call_tool("list_playlists", {})
    data = _parse_result(result)
    assert data["items"] == []
    assert data["total"] == 0


# ── manage_playlist ──────────────────────────────────


async def test_manage_playlist_create(client: Client):
    """manage_playlist create makes a new playlist."""
    result = await client.call_tool(
        "manage_playlist",
        {"action": "create", "data": {"name": "My Playlist"}},
    )
    data = _parse_result(result)
    assert data["name"] == "My Playlist"
    assert "id" in data


# ── list_sets ────────────────────────────────────────


async def test_list_sets_empty(client: Client):
    """list_sets on empty db returns no items."""
    result = await client.call_tool("list_sets", {})
    data = _parse_result(result)
    assert data["items"] == []


# ── manage_set ───────────────────────────────────────


async def test_manage_set_create(client: Client):
    """manage_set create makes a new DJ set."""
    result = await client.call_tool(
        "manage_set",
        {"action": "create", "data": {"name": "Friday Night Set"}},
    )
    data = _parse_result(result)
    assert data["name"] == "Friday Night Set"
    assert "id" in data


# ── get_track_features ───────────────────────────────


async def test_get_track_features_no_features(client: Client, async_engine):
    """get_track_features returns has_features=False when no analysis done."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        track = Track(title="Unanalyzed")
        session.add(track)
        await session.flush()
        track_id = track.id
        await session.commit()

    result = await client.call_tool("get_track_features", {"id": track_id})
    data = _parse_result(result)
    assert data["has_features"] is False
    assert data["track_id"] == track_id
