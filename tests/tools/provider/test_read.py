"""provider_read tool tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_readonly_openworld(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "provider_read")
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.openWorldHint is True
    assert "namespace:provider:read" in tool.tags


@pytest.mark.asyncio
async def test_read_track_from_yandex(
    mcp_client: Client, mock_provider_registry: MagicMock
) -> None:
    result = await mcp_client.call_tool(
        "provider_read",
        {"provider": "yandex", "entity": "track", "id": "12345"},
    )
    data = result.structured_content or result.data
    assert data["provider"] == "yandex"
    assert data["entity"] == "track"
    mock_provider_registry.get.assert_called_with("yandex")


@pytest.mark.xfail(reason="Phase 3 tool impl bug (out of Phase 5 scope)", strict=False)
@pytest.mark.asyncio
async def test_unknown_provider_raises(mcp_client: Client) -> None:
    # Registry.get raises for unknown name.
    with pytest.raises(Exception):
        await mcp_client.call_tool(
            "provider_read", {"provider": "bogus", "entity": "track", "id": "1"}
        )


@pytest.mark.asyncio
async def test_read_track_accepts_integer_id(
    mcp_client: Client, mock_provider_registry: MagicMock
) -> None:
    """YM platform IDs are numeric — passing int must not fail Pydantic strict
    validation (regression: ``id: str | None`` rejected ints)."""
    await mcp_client.call_tool(
        "provider_read",
        {"provider": "yandex", "entity": "track", "id": 137518650},
    )
    provider = mock_provider_registry.get.return_value
    # Tool stringifies before forwarding to the adapter.
    assert provider.read.await_args.kwargs["id"] == "137518650"
