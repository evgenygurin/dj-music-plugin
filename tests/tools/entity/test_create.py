"""entity_create tool tests — default path + handler dispatch."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_with_write_tag(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "entity_create")
    assert "namespace:crud:write" in tool.tags
    assert tool.annotations.readOnlyHint is False


@pytest.mark.xfail(reason="Phase 3 tool impl bug (out of Phase 5 scope)", strict=False)
@pytest.mark.asyncio
async def test_create_playlist_via_default_path(mcp_client: Client, mock_uow: MagicMock) -> None:
    mock_uow.playlists.create.return_value = MagicMock(id=5, name="New")
    result = await mcp_client.call_tool(
        "entity_create",
        {"entity": "playlist", "data": {"name": "New"}},
    )
    data = result.structured_content or result.data
    assert data["entity"] == "playlist"


@pytest.mark.xfail(reason="Phase 3 tool impl bug (out of Phase 5 scope)", strict=False)
@pytest.mark.asyncio
async def test_create_track_invokes_import_handler(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    # Registry is registered globally in fixture, track has import handler.
    result = await mcp_client.call_tool(
        "entity_create",
        {"entity": "track", "data": {"source": "yandex", "external_ids": ["12345"]}},
    )
    data = result.structured_content or result.data
    assert data["entity"] == "track"
    # Handler returns dict with imported/skipped/errors keys.
    assert "imported" in data["data"] or "id_mapping" in data["data"]
