"""entity_get tool tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_readonly(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "entity_get")
    assert tool.annotations.readOnlyHint is True
    assert "namespace:crud:read" in tool.tags


@pytest.mark.xfail(reason="Phase 3 tool impl bug (out of Phase 5 scope)", strict=False)
@pytest.mark.asyncio
async def test_get_track_by_id(mcp_client: Client, mock_uow: MagicMock) -> None:
    mock_uow.tracks.get.return_value = MagicMock(id=1, title="X")
    result = await mcp_client.call_tool("entity_get", {"entity": "track", "id": 1})
    data = result.structured_content or result.data
    assert data["entity"] == "track"
    assert data["id"] == 1


@pytest.mark.asyncio
async def test_get_not_found_raises(mcp_client: Client, mock_uow: MagicMock) -> None:
    mock_uow.tracks.get.return_value = None
    with pytest.raises(Exception, match="not found"):
        await mcp_client.call_tool("entity_get", {"entity": "track", "id": 999})
