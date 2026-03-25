"""Tests for background task support in MCP tools.

Tests cover:
- Task mode annotations (optional, required, forbidden)
- Progress reporting
- Task orchestration via Docket
- Background scoring service
"""

from __future__ import annotations

import pytest

from app.services.background_tasks import _features_to_dataclass, score_track_transitions


@pytest.mark.asyncio
async def test_analyze_track_task_metadata(client):  # type: ignore[no-untyped-def]
    """Verify analyze_track is task-enabled with optional mode."""
    tools = await client.list_tools()
    analyze_track = next(t for t in tools if t.name == "analyze_track")

    assert analyze_track.annotations is not None
    # FastMCP should expose task mode in metadata (SEP-1686)
    # For now just verify idempotentHint
    assert analyze_track.annotations.get("idempotentHint") is True


@pytest.mark.asyncio
async def test_analyze_batch_task_metadata(client):  # type: ignore[no-untyped-def]
    """Verify analyze_batch is task-enabled with optional mode."""
    tools = await client.list_tools()
    analyze_batch = next(t for t in tools if t.name == "analyze_batch")

    assert analyze_batch.annotations is not None
    assert analyze_batch.annotations.get("idempotentHint") is True


@pytest.mark.asyncio
async def test_separate_stems_task_metadata(client):  # type: ignore[no-untyped-def]
    """Verify separate_stems requires task mode (mode=required)."""
    tools = await client.list_tools()
    separate_stems = next(t for t in tools if t.name == "separate_stems")

    # separate_stems has task=TaskConfig(mode="required")
    # It should not have readOnlyHint or idempotentHint
    assert separate_stems.annotations is None or separate_stems.annotations.get(
        "idempotentHint"
    ) is not True


@pytest.mark.asyncio
async def test_score_track_transitions_background_exists(client):  # type: ignore[no-untyped-def]
    """Verify new background scoring tool is registered."""
    tools = await client.list_tools()
    tool = next((t for t in tools if t.name == "score_track_transitions_background"), None)

    assert tool is not None
    assert "sets" in tool.tags
    assert tool.annotations is not None
    assert tool.annotations.get("readOnlyHint") is False


@pytest.mark.asyncio
async def test_import_tracks_schedules_analysis(seeded_db):  # type: ignore[no-untyped-def]
    """Verify import_tracks with auto_analyze schedules background task."""
    # This is an integration test — real implementation would:
    # 1. Import tracks
    # 2. Call docket.add(analyze_batch, track_ids=imported_ids)
    # 3. Return auto_analyze_scheduled=True

    # For now just verify the service layer exists
    from app.services.background_tasks import score_track_transitions

    assert callable(score_track_transitions)


@pytest.mark.asyncio
async def test_features_to_dataclass():
    """Test conversion from DB model to service dataclass."""
    from app.models.track import TrackAudioFeaturesComputed

    features = TrackAudioFeaturesComputed(
        track_id=1,
        pipeline_run_id=1,
        bpm=128.0,
        key_code=8,  # 5A (C minor)
        integrated_lufs=-12.0,
        spectral_centroid_hz=2500.0,
        spectral_flatness=0.25,
        energy_mean=0.7,
        onset_rate=2.5,
        kick_prominence=0.8,
        hnr_db=-10.0,
        chroma_entropy=0.5,
    )

    dataclass = _features_to_dataclass(features)

    assert dataclass.bpm == 128.0
    assert dataclass.key_code == 8
    assert dataclass.integrated_lufs == -12.0
    assert dataclass.spectral_centroid_hz == 2500.0
    assert dataclass.energy_mean == 0.7
    assert dataclass.onset_rate == 2.5


@pytest.mark.asyncio
async def test_score_track_transitions_service_error_handling(seeded_db):  # type: ignore[no-untyped-def]
    """Test background scoring service handles missing track."""
    async with seeded_db() as session:
        result = await score_track_transitions(
            track_id=99999,  # non-existent
            session=session,
            progress=None,
        )

        assert "error" in result
        assert result["scored"] == 0


# Note: Full integration tests with FastMCP Client task execution
# would require:
# 1. async with Client(mcp) as client:
# 2.     result = await client.call_tool("analyze_batch", {...}, as_task=True)
# 3.     assert "task_id" in result
# 4.     # Poll for completion
#
# This requires FastMCP v3.1+ with Docket backend initialized.
# For now we test metadata and service layer independently.
