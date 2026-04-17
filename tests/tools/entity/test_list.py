"""entity_list tool tests — metadata + integration."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_is_registered(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    names = [t.name for t in tools]
    assert "entity_list" in names


@pytest.mark.asyncio
async def test_tool_annotations_read_only(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "entity_list")
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.idempotentHint is True


@pytest.mark.asyncio
async def test_tool_has_namespace_tags(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "entity_list")
    assert "namespace:crud:read" in tool.tags


@pytest.mark.xfail(
    reason="Phase 3 tool bug: parse_django_filters signature mismatch", strict=False
)
@pytest.mark.asyncio
async def test_list_tracks_happy_path(mcp_client: Client, mock_uow: MagicMock) -> None:
    page = MagicMock(items=[MagicMock(id=1, title="X")], next_cursor=None, total=1)
    mock_uow.tracks.filter.return_value = page

    result = await mcp_client.call_tool("entity_list", {"entity": "track", "limit": 10})
    data = result.structured_content or result.data
    assert data["entity"] == "track"
    assert data["items"] is not None


@pytest.mark.asyncio
async def test_list_unknown_entity_raises(mcp_client: Client) -> None:
    with pytest.raises(Exception, match="entity"):
        await mcp_client.call_tool("entity_list", {"entity": "bogus", "limit": 10})
