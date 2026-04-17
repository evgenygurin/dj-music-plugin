"""provider_write tool tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_write_openworld(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "provider_write")
    assert tool.annotations.readOnlyHint is False
    assert tool.annotations.openWorldHint is True
    assert "namespace:provider:write" in tool.tags


@pytest.mark.asyncio
async def test_add_tracks_to_playlist(
    mcp_client: Client, mock_provider_registry: MagicMock
) -> None:
    result = await mcp_client.call_tool(
        "provider_write",
        {
            "provider": "yandex",
            "entity": "playlist",
            "operation": "add_tracks",
            "params": {
                "playlist_id": "42:3",
                "track_ids": ["1", "2"],
                "revision": 7,
                "at": 0,
            },
        },
    )
    data = result.structured_content or result.data
    assert data["operation"] == "add_tracks"
    mock_provider_registry.get.return_value.write.assert_awaited()


@pytest.mark.asyncio
async def test_add_likes(mcp_client: Client, mock_provider_registry: MagicMock) -> None:
    mock_provider_registry.get.return_value.write.return_value = {"ok": True}
    result = await mcp_client.call_tool(
        "provider_write",
        {
            "provider": "yandex",
            "entity": "likes",
            "operation": "add",
            "params": {"track_ids": ["1", "2", "3"]},
        },
    )
    data = result.structured_content or result.data
    assert data["data"]["ok"] is True
