"""Tests for session://set-draft resource."""

from __future__ import annotations

import json

import pytest
from fastmcp import Client


def _read_resource_data(result) -> dict:  # type: ignore[no-untyped-def]
    """Extract dict from resource read result."""
    item = result[0] if result else None
    if item is None:
        return {}
    text = getattr(item, "text", None) or getattr(item, "content", None) or "{}"
    return json.loads(text) if isinstance(text, str) else (text or {})


@pytest.mark.asyncio
async def test_session_draft_resource_returns_empty_when_no_draft(client: Client):
    """session://set-draft returns {} when no draft has been set."""
    result = await client.read_resource("session://set-draft")
    data = _read_resource_data(result)
    assert data == {}


@pytest.mark.asyncio
async def test_session_draft_resource_returns_draft_after_update(client: Client):
    """session://set-draft reflects state after update_set_draft."""
    await client.call_tool(
        "update_set_draft",
        {
            "track_ids": [10, 20, 30],
            "name": "Resource Test Set",
        },
    )
    result = await client.read_resource("session://set-draft")
    data = _read_resource_data(result)
    assert data["track_ids"] == [10, 20, 30]
    assert data["name"] == "Resource Test Set"
