"""entity_update tool tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_with_destructive_tag(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "entity_update")
    assert "namespace:crud:destructive" in tool.tags
    assert tool.annotations.idempotentHint is True


@pytest.mark.asyncio
async def test_update_playlist_happy_path(mcp_client: Client, mock_uow: MagicMock) -> None:
    mock_uow.playlists.update.return_value = MagicMock(id=5, name="Renamed")
    result = await mcp_client.call_tool(
        "entity_update",
        {"entity": "playlist", "id": 5, "data": {"name": "Renamed"}},
    )
    data = result.structured_content or result.data
    assert data["id"] == 5


@pytest.mark.asyncio
async def test_update_not_found_raises(mcp_client: Client, mock_uow: MagicMock) -> None:
    mock_uow.playlists.update.side_effect = Exception("not found")
    with pytest.raises(Exception, match="not found"):
        await mcp_client.call_tool(
            "entity_update",
            {"entity": "playlist", "id": 999, "data": {"name": "X"}},
        )
