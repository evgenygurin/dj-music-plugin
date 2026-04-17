"""Tests for draft set tools (update, preview, commit, clear)."""

from __future__ import annotations

import json

import pytest
from fastmcp import Client

from tests.conftest import _parse_tool_result as _parse


def _read_draft(result) -> dict:  # type: ignore[no-untyped-def]
    item = result[0] if result else None
    text = getattr(item, "text", None) or "{}"
    return json.loads(text) if isinstance(text, str) else (text or {})


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
    data = _read_draft(result)
    assert data["track_ids"] == [10, 20, 30]
    assert data["name"] == "B"


@pytest.mark.asyncio
async def test_update_set_draft_rejects_empty_track_ids(client: Client):
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await client.call_tool("update_set_draft", {"track_ids": [], "name": "Empty"})


@pytest.mark.asyncio
async def test_update_set_draft_preserves_name_when_omitted(client: Client):
    """Second call without name keeps the name from the first call."""
    await client.call_tool("update_set_draft", {"track_ids": [1, 2], "name": "Keeper"})
    result = await client.call_tool("update_set_draft", {"track_ids": [3, 4]})
    data = _parse(result)
    assert data["name"] == "Keeper"


@pytest.mark.asyncio
async def test_update_set_draft_same_ids_no_duplicates(client: Client):
    """Calling with identical track_ids is idempotent — no list growth."""
    await client.call_tool("update_set_draft", {"track_ids": [5, 6, 7], "name": "Idem"})
    await client.call_tool("update_set_draft", {"track_ids": [5, 6, 7]})
    draft = _read_draft(await client.read_resource("session://set-draft"))
    assert draft["track_ids"] == [5, 6, 7]


@pytest.mark.asyncio
async def test_update_set_draft_accepts_set_name_alias(client: Client):
    """`set_name` alias should work for backward-compatible clients."""
    result = await client.call_tool(
        "update_set_draft",
        {"track_ids": [11, 12], "set_name": "Alias Name"},
    )
    data = _parse(result)
    assert data["name"] == "Alias Name"


# ── clear_draft ──────────────────────────────────────


@pytest.mark.asyncio
async def test_clear_draft_removes_state(client: Client):
    await client.call_tool("update_set_draft", {"track_ids": [1, 2, 3], "name": "ClearTest"})
    result = await client.call_tool("clear_draft", {})
    data = _parse(result)
    assert data["cleared"] is True

    draft = _read_draft(await client.read_resource("session://set-draft"))
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


@pytest.mark.asyncio
async def test_preview_draft_partial_features_does_not_crash(client: Client, async_engine):
    """preview_draft survives when only some tracks have audio features."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.audio import TrackAudioFeaturesComputed
    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    track_ids: list[int] = []
    async with factory() as session:
        for i in range(4):
            t = Track(title=f"Partial Track {i}", status=0, duration_ms=180000)
            session.add(t)
            await session.flush()
            track_ids.append(t.id)
            # Only even-indexed tracks get features
            if i % 2 == 0:
                session.add(
                    TrackAudioFeaturesComputed(
                        track_id=t.id,
                        bpm=128.0 + i,
                        key_code=5,
                        integrated_lufs=-10.0,
                        energy_mean=0.65,
                        spectral_centroid_hz=2200.0,
                        onset_rate=3.8,
                        kick_prominence=0.55,
                    )
                )
        await session.commit()

    await client.call_tool(
        "update_set_draft", {"track_ids": track_ids, "name": "Partial Features"}
    )
    result = await client.call_tool("preview_draft", {"narrative": False})
    data = _parse(result)
    # Must return valid structure without crashing
    assert "score" in data
    assert "track_count" in data
    assert data["track_count"] == 4


@pytest.mark.asyncio
async def test_preview_draft_single_track(client: Client, async_engine):
    """1-track draft has no transitions — score=1.0, empty weak_spots."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.audio import TrackAudioFeaturesComputed
    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        t = Track(title="Solo Track", status=0, duration_ms=240000)
        session.add(t)
        await session.flush()
        session.add(
            TrackAudioFeaturesComputed(
                track_id=t.id,
                bpm=132.0,
                key_code=3,
                integrated_lufs=-9.0,
                energy_mean=0.7,
                spectral_centroid_hz=2500.0,
                onset_rate=4.2,
                kick_prominence=0.65,
            )
        )
        await session.commit()
        track_id = t.id

    await client.call_tool("update_set_draft", {"track_ids": [track_id], "name": "Solo"})
    data = _parse(await client.call_tool("preview_draft", {}))
    assert data["score"] == 1.0
    assert data["weak_spots"] == []
    assert data["track_count"] == 1


@pytest.mark.asyncio
async def test_preview_draft_nonexistent_track_ids(client: Client):
    """Nonexistent IDs → preview_arc returns gracefully (all missing)."""
    await client.call_tool("update_set_draft", {"track_ids": [999_001, 999_002], "name": "Ghost"})
    # Should not raise — preview_arc handles an empty features_map
    data = _parse(await client.call_tool("preview_draft", {}))
    assert "score" in data
    assert data["track_count"] == 2


@pytest.mark.asyncio
async def test_preview_draft_accepts_stateless_track_ids(client: Client, async_engine):
    """preview_draft(track_ids=...) works without session draft state."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.audio import TrackAudioFeaturesComputed
    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    track_ids: list[int] = []
    async with factory() as session:
        for i in range(2):
            t = Track(title=f"Stateless Preview {i}", status=0, duration_ms=180000)
            session.add(t)
            await session.flush()
            track_ids.append(t.id)
            session.add(
                TrackAudioFeaturesComputed(
                    track_id=t.id,
                    bpm=129.0 + i,
                    key_code=6 + i,
                    integrated_lufs=-10.5,
                    energy_mean=0.62,
                    spectral_centroid_hz=2300.0,
                    onset_rate=3.9,
                    kick_prominence=0.58,
                )
            )
        await session.commit()

    data = _parse(await client.call_tool("preview_draft", {"track_ids": track_ids}))
    assert data["track_count"] == 2
    assert "score" in data


# ── commit_draft ─────────────────────────────────────


@pytest.mark.asyncio
async def test_commit_draft_raises_when_no_draft(client: Client):
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await client.call_tool("commit_draft", {})


@pytest.mark.asyncio
async def test_commit_draft_without_elicitation_handler_saves(client: Client, async_engine):
    """No elicitation_handler → commit saves directly, clears draft."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.track import Track
    from app.db.repositories.set import SetRepository

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        t = Track(title="NoElicit Track", status=0, duration_ms=180000)
        session.add(t)
        await session.commit()
        track_id = t.id

    # `client` fixture has no elicitation_handler — ctx.elicit() will raise,
    # commit_draft must catch and save anyway.
    await client.call_tool("update_set_draft", {"track_ids": [track_id], "name": "NoElicit Set"})
    result = _parse(await client.call_tool("commit_draft", {}))
    assert result["set_id"] > 0
    assert result["track_count"] == 1

    # Draft must be cleared
    draft = _read_draft(await client.read_resource("session://set-draft"))
    assert draft == {}

    # Version exists in DB
    async with factory() as session:
        repo = SetRepository(session)
        version = await repo.get_latest_version(result["set_id"])
    assert version is not None


@pytest.mark.asyncio
async def test_commit_draft_allows_set_name_override(client: Client, async_engine):
    """commit_draft(set_name=...) should override stored draft name for saved set."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.set import DjSet
    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        t = Track(title="Override Track", status=0, duration_ms=180000)
        session.add(t)
        await session.commit()
        track_id = t.id

    await client.call_tool("update_set_draft", {"track_ids": [track_id], "name": "Old Name"})
    result = _parse(await client.call_tool("commit_draft", {"set_name": "New Name"}))
    assert result["set_id"] > 0

    async with factory() as session:
        saved_set = (
            await session.execute(select(DjSet).where(DjSet.id == result["set_id"]))
        ).scalar_one()
    assert saved_set.name == "New Name"


@pytest.mark.asyncio
async def test_commit_draft_decline_returns_cancelled_no_db_write(
    client: Client, async_engine, monkeypatch
):
    """When ctx.elicit() returns action='decline', commit must cancel without DB write.

    NOTE: In-memory FastMCP transport raises on ctx.elicit() even when an
    elicitation_handler is attached (transport limitation). We therefore patch
    Context.elicit at class level to return a decline result directly — this
    isolates the commit_draft branch logic from the transport implementation.
    """
    from fastmcp.server.context import Context
    from fastmcp.server.elicitation import DeclinedElicitation
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        t = Track(title="Decline Track", status=0, duration_ms=180000)
        session.add(t)
        await session.commit()
        track_id = t.id

    async def _fake_elicit(self, message, *, response_type=None, **kwargs):  # type: ignore[no-untyped-def]
        return DeclinedElicitation()

    monkeypatch.setattr(Context, "elicit", _fake_elicit)

    await client.call_tool("update_set_draft", {"track_ids": [track_id], "name": "Decline Test"})
    result = _parse(await client.call_tool("commit_draft", {}))
    assert result.get("cancelled") is True, f"Expected cancelled=True, got: {result}"

    # Verify nothing was written to DB
    from sqlalchemy import select

    from app.db.models.set import DjSet

    async with factory() as session:
        count = len((await session.execute(select(DjSet))).scalars().all())
    assert count == 0, f"Expected no sets in DB after decline, found {count}"


@pytest.mark.asyncio
async def test_commit_draft_db_error_propagates(client: Client, async_engine, monkeypatch):
    """An exception from svc.commit_version must NOT be silently swallowed."""
    from fastmcp.exceptions import ToolError
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        t = Track(title="Err Track", status=0, duration_ms=180000)
        session.add(t)
        await session.commit()
        track_id = t.id

    async def _boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("DB exploded")

    monkeypatch.setattr("app.services.set.facade.SetService.commit_version", _boom)

    await client.call_tool("update_set_draft", {"track_ids": [track_id], "name": "Err Set"})
    with pytest.raises((ToolError, RuntimeError)):
        await client.call_tool("commit_draft", {})


@pytest.mark.asyncio
async def test_commit_draft_accepts_stateless_track_ids(client: Client, async_engine):
    """commit_draft(track_ids=...) saves set without pre-existing session draft."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    track_ids: list[int] = []
    async with factory() as session:
        for i in range(2):
            t = Track(title=f"Stateless Commit {i}", status=0, duration_ms=180000)
            session.add(t)
            await session.flush()
            track_ids.append(t.id)
        await session.commit()

    result = _parse(
        await client.call_tool(
            "commit_draft",
            {"track_ids": track_ids, "set_name": "Stateless Commit"},
        )
    )
    assert result["set_id"] > 0
    assert result["track_count"] == 2


# ── _generate_narrative — sample_structured / ctx.sample fallback ─


@pytest.mark.asyncio
async def test_generate_narrative_metrics_fallback_when_sample_raises():
    """When sampling raises, return metrics-only ArcCritique (no API key required)."""
    from unittest.mock import AsyncMock, MagicMock

    from app.controllers.tools.draft import _generate_narrative
    from app.optimization.preview import PreviewResult

    ctx = MagicMock()
    ctx.sample = AsyncMock(side_effect=Exception("LLM unavailable"))
    ctx.warning = AsyncMock()

    mock_resource_result = MagicMock()
    mock_resource_result.contents = []
    ctx.read_resource = AsyncMock(return_value=mock_resource_result)

    result = PreviewResult(
        score=0.7,
        energy_arc=[-10.0, -11.0],
        bpm_arc=[130.0, 132.0],
        weak_spots=[],
        recommendation="Decent arc.",
        missing_track_ids=[],
    )

    output = await _generate_narrative(ctx, result, [1, 2])
    assert output is not None
    assert "[Metrics-only]" in output["crowd_journey"]
    assert output["recommendation"] == "Decent arc."
    ctx.warning.assert_called_once()


# ── score_transitions — ctx=None regression ──────────


@pytest.mark.asyncio
async def test_score_transitions_reports_progress():
    """score_transitions reports progress via ctx.report_progress (no None guard)."""
    from unittest.mock import AsyncMock, MagicMock

    from app.controllers.tools.sets import score_transitions

    mock_workflow = AsyncMock()
    mock_workflow.score_transitions.return_value = {"scored": 1, "transitions": []}

    ctx = MagicMock()
    ctx.report_progress = AsyncMock()

    result = await score_transitions(
        mode="pair",
        from_track_id=1,
        to_track_id=2,
        workflow=mock_workflow,
        ctx=ctx,
    )
    assert isinstance(result, dict)
    assert ctx.report_progress.call_count >= 1
    mock_workflow.score_transitions.assert_awaited_once()


@pytest.mark.asyncio
async def test_score_transitions_count_alias_overrides_top_n():
    """count alias should override top_n when forwarding to workflow."""
    from unittest.mock import AsyncMock, MagicMock

    from app.controllers.tools.sets import score_transitions

    mock_workflow = AsyncMock()
    mock_workflow.score_transitions.return_value = {"mode": "track_candidates", "candidates": []}

    ctx = MagicMock()
    ctx.report_progress = AsyncMock()

    await score_transitions(
        mode="track_candidates",
        track_id=42,
        top_n=10,
        count=3,
        workflow=mock_workflow,
        ctx=ctx,
    )

    kwargs = mock_workflow.score_transitions.await_args.kwargs
    assert kwargs["top_n"] == 3
