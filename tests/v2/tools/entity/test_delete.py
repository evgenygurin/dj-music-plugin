"""entity_delete tool tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_destructive(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "entity_delete")
    assert tool.annotations.destructiveHint is True
    assert "namespace:crud:destructive" in tool.tags


@pytest.mark.asyncio
async def test_delete_playlist(mcp_client: Client, mock_uow: MagicMock) -> None:
    result = await mcp_client.call_tool("entity_delete", {"entity": "playlist", "id": 5})
    data = result.structured_content or result.data
    assert data["deleted"] is True
    mock_uow.playlists.delete.assert_awaited_once_with(5)
