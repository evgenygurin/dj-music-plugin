"""get_transition_candidates tool tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client

from app.domain.transition.score import TransitionScore


@pytest.mark.asyncio
async def test_tool_registered_readonly(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "get_transition_candidates")
    assert tool.annotations.readOnlyHint is True
    assert "namespace:compute" in tool.tags


@pytest.mark.asyncio
async def test_missing_source_features_returns_analyze_first(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(return_value={})
    result = await mcp_client.call_tool("get_transition_candidates", {"track_id": 1})
    data = result.structured_content or result.data
    assert data["missing_features"] is True
    assert data["candidates"] == []


@pytest.mark.asyncio
async def test_no_analyzed_tracks(mcp_client: Client, mock_uow: MagicMock) -> None:
    src_feat = MagicMock(bpm=128.0, key_code=1)
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(
        side_effect=lambda ids: {1: src_feat} if ids == [1] else {}
    )
    mock_uow.tracks.filter = AsyncMock(return_value=MagicMock(items=[], next_cursor=None))
    result = await mcp_client.call_tool("get_transition_candidates", {"track_id": 1})
    data = result.structured_content or result.data
    assert data["total_analyzed"] == 0
    assert data["candidates"] == []


@pytest.mark.asyncio
async def test_excludes_source_track(mcp_client: Client, mock_uow: MagicMock) -> None:
    src_feat = MagicMock(bpm=128.0, key_code=1)
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(
        side_effect=lambda ids: {1: src_feat} if 1 in ids else {2: MagicMock(bpm=130.0)}
    )
    mock_uow.tracks.filter = AsyncMock(
        return_value=MagicMock(items=[MagicMock(id=1), MagicMock(id=2)], next_cursor=None)
    )
    mock_uow.tracks.get_many = AsyncMock(return_value={2: MagicMock(title="Other")})

    result = await mcp_client.call_tool("get_transition_candidates", {"track_id": 1})
    data = result.structured_content or result.data
    assert data["total_analyzed"] == 1
    for c in data["candidates"]:
        assert c["track_id"] != 1


@pytest.mark.asyncio
async def test_returns_top_k_candidates(
    mcp_client: Client, mock_uow: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    scorer_mock = MagicMock()
    scorer_mock.score.return_value = TransitionScore(overall=0.85, bpm=0.9, energy=0.8)

    from app.server import di

    _original = di._read_slot

    async def _patched_read_slot(ctx, key, what):
        if key == "transition_scorer":
            return scorer_mock
        return await _original(ctx, key, what)

    monkeypatch.setattr(di, "_read_slot", _patched_read_slot)

    src_feat = MagicMock(bpm=128.0, key_code=1)
    feat_map = {1: src_feat}
    for tid in range(2, 12):
        feat_map[tid] = MagicMock(bpm=128.0 + tid, key_code=1)

    mock_uow.track_features.get_scoring_features_batch = AsyncMock(
        side_effect=lambda ids: {tid: feat_map[tid] for tid in ids if tid in feat_map}
    )
    mock_uow.tracks.filter = AsyncMock(
        return_value=MagicMock(
            items=[MagicMock(id=i) for i in range(1, 12)],
            next_cursor=None,
        )
    )
    mock_uow.tracks.get_many = AsyncMock(
        return_value={i: MagicMock(title=f"Track {i}") for i in range(2, 12)}
    )

    result = await mcp_client.call_tool("get_transition_candidates", {"track_id": 1, "top_k": 3})
    data = result.structured_content or result.data
    assert len(data["candidates"]) <= 3


@pytest.mark.asyncio
async def test_min_score_filters_low_scores(
    mcp_client: Client, mock_uow: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    scorer_mock = MagicMock()

    def score_side_effect(src, to):
        tid = to.bpm  # use bpm field to differentiate tracks
        if tid and tid > 130:
            return TransitionScore(overall=0.5, hard_reject=False)
        return TransitionScore(overall=0.9, hard_reject=False)

    scorer_mock.score.side_effect = score_side_effect

    from app.server import di

    _original = di._read_slot

    async def _patched_read_slot(ctx, key, what):
        if key == "transition_scorer":
            return scorer_mock
        return await _original(ctx, key, what)

    monkeypatch.setattr(di, "_read_slot", _patched_read_slot)

    src_feat = MagicMock(bpm=128.0, key_code=1)
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(
        side_effect=lambda ids: (
            {
                1: src_feat,
                2: MagicMock(bpm=125.0, key_code=3),
                3: MagicMock(bpm=135.0, key_code=5),
            }
            if set(ids) & {1, 2, 3}
            else {}
        )
    )
    mock_uow.tracks.filter = AsyncMock(
        return_value=MagicMock(
            items=[MagicMock(id=1), MagicMock(id=2), MagicMock(id=3)],
            next_cursor=None,
        )
    )
    mock_uow.tracks.get_many = AsyncMock(
        return_value={2: MagicMock(title="A"), 3: MagicMock(title="B")}
    )

    result = await mcp_client.call_tool(
        "get_transition_candidates", {"track_id": 1, "min_score": 0.8, "top_k": 10}
    )
    data = result.structured_content or result.data
    for c in data["candidates"]:
        assert c["overall"] >= 0.8
