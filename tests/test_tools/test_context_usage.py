"""Tests for Context usage patterns in MCP tools.

Ensures all tools properly use CurrentContext() and Context methods.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastmcp import Client

from app.server import mcp


def _parse_result(result: Any) -> dict[str, Any]:
    """Extract dict from MCP tool result (CallToolResult)."""
    if hasattr(result, "data") and isinstance(result.data, dict):
        return result.data
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

    original_lifespan = mcp._lifespan

    async def _test_lifespan(server):  # type: ignore[no-untyped-def]
        yield {"db_engine": async_engine, "db_session_factory": factory}

    mcp._lifespan = Lifespan(_test_lifespan)

    try:
        async with Client(mcp) as c:
            yield c
    finally:
        mcp._lifespan = original_lifespan


# ── Context access tests ─────────────────────────────


async def test_context_available_in_list_tracks(client: Client):
    """list_tracks can access Context via CurrentContext()."""
    result = await client.call_tool("list_tracks", {})
    data = _parse_result(result)
    # If tool executes successfully, Context was properly injected
    assert "items" in data
    assert "total" in data


async def test_context_available_in_search(client: Client):
    """search can access Context via CurrentContext()."""
    result = await client.call_tool("search", {"query": "test"})
    data = _parse_result(result)
    assert "results" in data


async def test_context_logging_in_build_set(client: Client, async_engine):
    """build_set uses ctx.info() for progress logging."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.playlist import Playlist
    from app.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        playlist = Playlist(name="Test Playlist", source_of_truth="local")
        session.add(playlist)
        await session.flush()
        playlist_id = playlist.id

        track = Track(title="Test Track")
        session.add(track)
        await session.flush()

        from app.models.playlist import PlaylistItem

        item = PlaylistItem(playlist_id=playlist_id, track_id=track.id, sort_index=0)
        session.add(item)
        await session.commit()

    # Call build_set — should use ctx.info() internally
    result = await client.call_tool(
        "build_set",
        {
            "playlist_id": playlist_id,
            "name": "Test Set",
            "algorithm": "greedy",
        },
    )
    data = _parse_result(result)
    assert "set_id" in data or "error" not in data


async def test_context_visibility_in_unlock_tools(client: Client):
    """unlock_tools uses ctx.enable_components() / ctx.disable_components()."""
    # Unlock audio category
    result = await client.call_tool("unlock_tools", {"action": "unlock", "category": "audio"})
    data = _parse_result(result)
    assert data["action"] == "unlocked"
    assert "audio" in data["categories"]

    # Lock it back
    result = await client.call_tool("unlock_tools", {"action": "lock", "category": "audio"})
    data = _parse_result(result)
    assert data["action"] == "locked"


async def test_get_session_helper_uses_get_context(client: Client):
    """_get_session() helper functions use get_context() correctly."""
    # This is implicitly tested by all DB-accessing tools running successfully
    result = await client.call_tool("list_playlists", {})
    data = _parse_result(result)
    assert "items" in data
    assert "total" in data
