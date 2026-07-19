"""get_transition_candidates tool tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client

from app.domain.transition.score import TransitionScore
from app.tools.compute.transition_candidates import get_transition_candidates


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

    assert data["from_track_id"] == 1
    assert data["missing_features"] is True
    assert data["candidates"] == []


@pytest.mark.asyncio
async def test_scores_analyzed_library_and_excludes_source_track(
    mock_uow: MagicMock,
) -> None:
    scorer = MagicMock()
    scorer.score.return_value = TransitionScore(overall=0.85, hard_reject=False)
    ctx = MagicMock()
    ctx.report_progress = AsyncMock()

    src_feat = SimpleNamespace(bpm=128.0, key_code=1)
    to_feat = SimpleNamespace(bpm=130.0, key_code=3, energy_mean=0.7, mood="peak_time")
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(
        side_effect=lambda ids: {
            tid: feat for tid, feat in {1: src_feat, 2: to_feat}.items() if tid in ids
        }
    )
    mock_uow.tracks.filter = AsyncMock(
        return_value=SimpleNamespace(
            items=[SimpleNamespace(id=1), SimpleNamespace(id=2)], next_cursor=None
        )
    )
    mock_uow.tracks.get_many = AsyncMock(return_value={2: SimpleNamespace(title="Other")})

    result = await get_transition_candidates(track_id=1, uow=mock_uow, scorer=scorer, ctx=ctx)
    data = result.model_dump()

    assert data["total_analyzed"] == 1
    assert [c["track_id"] for c in data["candidates"]] == [2]
    assert data["candidates"][0]["title"] == "Other"


@pytest.mark.asyncio
async def test_top_k_min_score_and_hard_reject_filter_candidates(
    mock_uow: MagicMock,
) -> None:
    scorer = MagicMock()

    def _score(_src: object, to_feat: SimpleNamespace) -> TransitionScore:
        if to_feat.track_id == 2:
            return TransitionScore(overall=0.9, hard_reject=False)
        if to_feat.track_id == 3:
            return TransitionScore(overall=0.7, hard_reject=False)
        return TransitionScore(overall=0.95, hard_reject=True, reject_reason="clash")

    scorer.score.side_effect = _score

    ctx = MagicMock()
    ctx.report_progress = AsyncMock()

    src_feat = SimpleNamespace(track_id=1, bpm=128.0, key_code=1)
    feat_map = {
        1: src_feat,
        2: SimpleNamespace(track_id=2, bpm=130.0, key_code=3, energy_mean=0.8, mood="peak_time"),
        3: SimpleNamespace(track_id=3, bpm=131.0, key_code=4, energy_mean=0.6, mood="driving"),
        4: SimpleNamespace(track_id=4, bpm=132.0, key_code=5, energy_mean=0.9, mood="dark"),
    }
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(
        side_effect=lambda ids: {tid: feat_map[tid] for tid in ids if tid in feat_map}
    )
    mock_uow.tracks.filter = AsyncMock(
        return_value=SimpleNamespace(
            items=[SimpleNamespace(id=i) for i in range(1, 5)], next_cursor=None
        )
    )
    mock_uow.tracks.get_many = AsyncMock(
        return_value={2: SimpleNamespace(title="Best"), 3: SimpleNamespace(title="Too Low")}
    )

    result = await get_transition_candidates(
        track_id=1,
        top_k=1,
        min_score=0.8,
        uow=mock_uow,
        scorer=scorer,
        ctx=ctx,
    )
    data = result.model_dump()

    assert [c["track_id"] for c in data["candidates"]] == [2]
    assert data["candidates"][0]["overall"] == 0.9
    assert data["candidates"][0]["title"] == "Best"
