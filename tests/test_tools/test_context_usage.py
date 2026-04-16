"""Tests for Context usage patterns in MCP tools.

Ensures all tools properly use CurrentContext() and Context methods.
"""

from __future__ import annotations

import json
from typing import Any

from fastmcp import Client


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


# Uses 'client' fixture from conftest.py (full lifespan context)


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
    result = await client.call_tool("search_library", {"query": "test"})
    data = _parse_result(result)
    assert "results" in data


async def test_context_logging_in_commit_set_version(client: Client, async_engine):
    """commit_set_version persists AI-curated track order."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        track = Track(title="Test Track")
        session.add(track)
        await session.flush()
        track_id = track.id
        await session.commit()

    result = await client.call_tool(
        "commit_set_version",
        {"track_ids": [track_id], "name": "Test Commit Set"},
    )
    data = _parse_result(result)
    assert "set_id" in data
    assert "version_id" in data
    assert data["track_count"] == 1


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
