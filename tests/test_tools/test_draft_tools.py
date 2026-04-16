"""Tests for draft set tools (update, preview, commit, clear)."""

from __future__ import annotations

import json

import pytest
from fastmcp import Client

from tests.conftest import _parse_tool_result as _parse

# ── update_set_draft ─────────────────────────────────


@pytest.mark.asyncio
async def test_update_set_draft_stores_track_ids(client: Client):
    result = await client.call_tool(
        "update_set_draft",
        {
            "track_ids": [1, 2, 3],
            "name": "Test Draft",
        },
    )
    data = _parse(result)
    assert data["track_count"] == 3
    assert data["name"] == "Test Draft"
    assert data["updated"] is True


@pytest.mark.asyncio
async def test_update_set_draft_replaces_previous(client: Client):
    await client.call_tool("update_set_draft", {"track_ids": [1, 2], "name": "A"})
    await client.call_tool("update_set_draft", {"track_ids": [10, 20, 30], "name": "B"})
    result = await client.read_resource("session://set-draft")
    item = result[0] if result else None
    text = getattr(item, "text", None) or "{}"
    data = json.loads(text) if isinstance(text, str) else (text or {})
    assert data["track_ids"] == [10, 20, 30]
    assert data["name"] == "B"


@pytest.mark.asyncio
async def test_update_set_draft_rejects_empty_track_ids(client: Client):
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await client.call_tool("update_set_draft", {"track_ids": [], "name": "Empty"})


# ── clear_draft ──────────────────────────────────────


@pytest.mark.asyncio
async def test_clear_draft_removes_state(client: Client):
    await client.call_tool("update_set_draft", {"track_ids": [1, 2, 3], "name": "ClearTest"})
    result = await client.call_tool("clear_draft", {})
    data = _parse(result)
    assert data["cleared"] is True

    resource_result = await client.read_resource("session://set-draft")
    item = resource_result[0] if resource_result else None
    text = getattr(item, "text", None) or "{}"
    draft = json.loads(text) if isinstance(text, str) else (text or {})
    assert draft == {}


@pytest.mark.asyncio
async def test_clear_draft_on_empty_session_is_safe(client: Client):
    result = await client.call_tool("clear_draft", {})
    data = _parse(result)
    assert data["cleared"] is True


# ── preview_draft — fast mode ────────────────────────


@pytest.mark.asyncio
async def test_preview_draft_raises_when_no_draft(client: Client):
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await client.call_tool("preview_draft", {})


@pytest.mark.asyncio
async def test_preview_draft_returns_arc_fields(client: Client, async_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.audio import TrackAudioFeaturesComputed
    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    track_ids: list[int] = []
    async with factory() as session:
        for i in range(3):
            t = Track(title=f"Preview Track {i}", status=0, duration_ms=180000)
            session.add(t)
            await session.flush()
            track_ids.append(t.id)
            session.add(
                TrackAudioFeaturesComputed(
                    track_id=t.id,
                    bpm=130.0 + i,
                    key_code=8 + i,
                    integrated_lufs=-11.0,
                    energy_mean=0.6 + i * 0.05,
                    spectral_centroid_hz=2400.0,
                    onset_rate=4.0,
                    kick_prominence=0.6,
                )
            )
        await session.commit()

    await client.call_tool(
        "update_set_draft",
        {
            "track_ids": track_ids,
            "name": "Preview Test",
        },
    )

    result = await client.call_tool("preview_draft", {"narrative": False})
    data = _parse(result)
    assert "score" in data
    assert "energy_arc" in data
    assert "bpm_arc" in data
    assert "weak_spots" in data
    assert "track_count" in data
    assert data["track_count"] == 3
    assert "critique" not in data  # narrative=False → no critique


# ── commit_draft ─────────────────────────────────────


@pytest.mark.asyncio
async def test_commit_draft_raises_when_no_draft(client: Client):
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await client.call_tool("commit_draft", {})
