"""Tests for CRUD MCP tools via FastMCP Client."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastmcp import Client

from app.server import mcp


def _parse_result(result: Any) -> dict[str, Any]:
    """Extract dict from MCP tool result (CallToolResult)."""
    # FastMCP Client.call_tool returns CallToolResult with .data attribute
    if hasattr(result, "data") and isinstance(result.data, dict):
        return result.data
    # Fallback: parse from content blocks
    content = getattr(result, "content", result)
    if isinstance(content, list) and len(content) > 0:
        block = content[0]
        text = getattr(block, "text", None) or str(block)
        return json.loads(text)
    if isinstance(result, dict):
        return result
    raise ValueError(f"Unexpected result type: {type(result)}")


@pytest.fixture
async def client(async_engine):
    """FastMCP test client with in-memory DB session factory."""
    from fastmcp.server.lifespan import Lifespan
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(async_engine, expire_on_commit=False)

    # Patch the user-provided lifespan so tools can get a session
    original_lifespan = mcp._lifespan

    async def _test_lifespan(server):  # type: ignore[no-untyped-def]
        yield {"db_engine": async_engine, "db_session_factory": factory}

    mcp._lifespan = Lifespan(_test_lifespan)

    try:
        async with Client(mcp) as c:
            yield c
    finally:
        mcp._lifespan = original_lifespan


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

    from app.models.track import Track

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

    from app.models.track import Track

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

    from app.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        session.add(Track(title="Aphex Twin - Xtal"))
        await session.commit()

    result = await client.call_tool("get_track", {"query": "Aphex"})
    data = _parse_result(result)
    assert "Aphex" in data["title"]


async def test_get_track_not_found(client: Client):
    """get_track returns error when not found."""
    result = await client.call_tool("get_track", {"id": 999})
    data = _parse_result(result)
    assert "error" in data


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

    from app.models.track import Track

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

    from app.models.track import Track

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
    """manage_tracks rejects invalid action."""
    result = await client.call_tool("manage_tracks", {"action": "explode"})
    data = _parse_result(result)
    assert "error" in data


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

    from app.models.track import Track

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


# ── Pagination integration tests ────────────────────────


async def test_list_tracks_pagination_no_overlap(client: Client, async_engine):
    """Verify pagination returns all items without overlap or gaps."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.track import Track

    # Seed 25 tracks
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        for i in range(25):
            session.add(Track(title=f"Track {i:02d}"))
        await session.commit()

    # Fetch all pages with page_size=10
    all_ids = []
    cursor = None
    page_count = 0

    while True:
        result = await client.call_tool("list_tracks", {"limit": 10, "cursor": cursor})
        data = _parse_result(result)
        
        page_count += 1
        assert data["total"] == 25
        
        for item in data["items"]:
            assert item["id"] not in all_ids, f"Duplicate ID {item['id']} in page {page_count}"
            all_ids.append(item["id"])
        
        cursor = data["next_cursor"]
        if cursor is None:
            break
        
        assert page_count <= 3, "Should not need more than 3 pages for 25 items"

    assert len(all_ids) == 25
    assert page_count == 3  # 10 + 10 + 5


async def test_list_tracks_pagination_cursor_stability(client: Client, async_engine):
    """Verify cursor is stable across identical requests."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        for i in range(20):
            session.add(Track(title=f"Track {i}"))
        await session.commit()

    # Get first page twice
    result1 = await client.call_tool("list_tracks", {"limit": 10})
    data1 = _parse_result(result1)
    
    result2 = await client.call_tool("list_tracks", {"limit": 10})
    data2 = _parse_result(result2)
    
    # Same items and same cursor
    assert data1["items"] == data2["items"]
    assert data1["next_cursor"] == data2["next_cursor"]


async def test_list_playlists_pagination(client: Client, async_engine):
    """Verify playlist pagination works correctly."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.playlist import Playlist

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        for i in range(15):
            session.add(Playlist(name=f"Playlist {i}", source_of_truth="local"))
        await session.commit()

    # First page
    result = await client.call_tool("list_playlists", {"limit": 10})
    data = _parse_result(result)
    assert len(data["items"]) == 10
    assert data["total"] == 15
    assert data["next_cursor"] is not None

    # Second page
    result = await client.call_tool("list_playlists", {"limit": 10, "cursor": data["next_cursor"]})
    data = _parse_result(result)
    assert len(data["items"]) == 5
    assert data["total"] == 15
    assert data["next_cursor"] is None
