"""entity_aggregate tool tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_readonly(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "entity_aggregate")
    assert tool.annotations.readOnlyHint is True


@pytest.mark.asyncio
async def test_count_tracks(mcp_client: Client, mock_uow: MagicMock) -> None:
    mock_uow.tracks.aggregate.return_value = 1234
    result = await mcp_client.call_tool(
        "entity_aggregate", {"entity": "track", "operation": "count"}
    )
    data = result.structured_content or result.data
    assert data["operation"] == "count"
    assert data["value"] == 1234


@pytest.mark.asyncio
async def test_histogram_by_mood(mcp_client: Client, mock_uow: MagicMock) -> None:
    mock_uow.tracks.aggregate.return_value = [
        {"mood": "peak_time", "count": 120},
        {"mood": "hypnotic", "count": 80},
    ]
    result = await mcp_client.call_tool(
        "entity_aggregate",
        {"entity": "track", "operation": "histogram", "group_by": "mood"},
    )
    data = result.structured_content or result.data
    assert isinstance(data["value"], list)
    assert len(data["value"]) == 2
