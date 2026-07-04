"""transition_score_pool tool tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_readonly(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "transition_score_pool")
    assert tool.annotations.readOnlyHint is True
    assert "namespace:compute" in tool.tags


@pytest.mark.asyncio
async def test_empty_pool_returns_empty(mcp_client: Client, mock_uow: MagicMock) -> None:
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(return_value={})
    result = await mcp_client.call_tool("transition_score_pool", {"track_ids": []})
    data = result.structured_content or result.data
    assert data["pairs"] == []


@pytest.mark.asyncio
async def test_scores_all_pairs_excluding_self(mcp_client: Client, mock_uow: MagicMock) -> None:
    features = {1: MagicMock(), 2: MagicMock(), 3: MagicMock()}
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(return_value=features)
    result = await mcp_client.call_tool("transition_score_pool", {"track_ids": [1, 2, 3]})
    data = result.structured_content or result.data
    # N*(N-1) = 6 directed pairs
    assert len(data["pairs"]) == 6
    for pair in data["pairs"]:
        assert pair["a"] != pair["b"]


@pytest.mark.asyncio
async def test_reports_progress(mcp_client: Client, mock_uow: MagicMock) -> None:
    features = {i: MagicMock() for i in range(1, 5)}
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(return_value=features)
    # Progress reporting is internal; tool just should complete without error.
    result = await mcp_client.call_tool("transition_score_pool", {"track_ids": [1, 2, 3, 4]})
    data = result.structured_content or result.data
    assert len(data["pairs"]) == 12  # 4*3


@pytest.mark.asyncio
async def test_top_k_caps_outgoing_pairs_per_track(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    features = {i: MagicMock() for i in range(1, 5)}
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(return_value=features)
    result = await mcp_client.call_tool(
        "transition_score_pool", {"track_ids": [1, 2, 3, 4], "top_k": 1}
    )
    data = result.structured_content or result.data
    # 4 source tracks x top_k=1 — but the full 4*3 matrix was scored.
    assert len(data["pairs"]) == 4
    assert data["total_scored_pairs"] == 12
    sources = [pair["a"] for pair in data["pairs"]]
    assert sorted(sources) == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_components_false_strips_stem_fields(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    features = {1: MagicMock(), 2: MagicMock()}
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(return_value=features)
    result = await mcp_client.call_tool(
        "transition_score_pool", {"track_ids": [1, 2], "components": False}
    )
    data = result.structured_content or result.data
    assert len(data["pairs"]) == 2
    for pair in data["pairs"]:
        assert set(pair) == {"a", "b", "overall"}


@pytest.mark.asyncio
async def test_full_response_keeps_component_fields_and_counts(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    features = {1: MagicMock(), 2: MagicMock()}
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(return_value=features)
    result = await mcp_client.call_tool("transition_score_pool", {"track_ids": [1, 2]})
    data = result.structured_content or result.data
    assert data["total_scored_pairs"] == 2
    for pair in data["pairs"]:
        assert set(pair) == {
            "a",
            "b",
            "overall",
            "bpm",
            "harmonics",
            "energy",
            "bass",
            "drums",
            "vocals",
        }
