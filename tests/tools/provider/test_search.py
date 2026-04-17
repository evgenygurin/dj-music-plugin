"""provider_search tool tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_readonly(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "provider_search")
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.openWorldHint is True


@pytest.mark.asyncio
async def test_search_tracks(mcp_client: Client, mock_provider_registry: MagicMock) -> None:
    result = await mcp_client.call_tool(
        "provider_search",
        {"provider": "yandex", "query": "techno", "type": "tracks", "limit": 10},
    )
    data = result.structured_content or result.data
    assert data["provider"] == "yandex"
    assert data["query"] == "techno"
    assert data["total"] >= 0


@pytest.mark.asyncio
async def test_limit_bounds(mcp_client: Client) -> None:
    with pytest.raises(Exception):
        await mcp_client.call_tool(
            "provider_search",
            {"provider": "yandex", "query": "x", "type": "tracks", "limit": 10000},
        )
