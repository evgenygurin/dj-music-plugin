"""Transport-parity regression for v1.1.0.

Same MCP call must work under both transports:

- ``mcp_client`` (native types - what existing tests use; what
  ``fastmcp.Client`` in-memory always does).
- ``stringified_mcp_client`` (proxy that JSON-stringifies dict/list
  args - what Claude Code stdio shim does in production).

Pins the v1.0.10-v1.0.13 transport-asymmetry bug class: any future
regression that breaks under stringified-args fails this test in CI
instead of falling on a user.

The test deliberately runs against ``mcp_server`` configured WITHOUT
middleware (``with_middleware=False`` in ``tests/tools/conftest.py``),
so the v1.1.0 server-side coercion middleware is NOT active here.
That means tools must remain robust via per-param ``Json*`` helpers
(belt-and-suspenders) even when the middleware is absent - a property
this test pins.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
async def test_entity_get_native_list(mcp_client: Any, mock_uow: MagicMock) -> None:
    """``include_relations`` must accept a native list."""
    mock_uow.tracks.get.return_value = None
    with pytest.raises(Exception, match="not found"):
        await mcp_client.call_tool(
            "entity_get",
            {
                "entity": "track",
                "id": 999,
                "include_relations": ["features", "artists"],
            },
        )


@pytest.mark.asyncio
async def test_entity_get_stringified_list(
    stringified_mcp_client: Any, mock_uow: MagicMock
) -> None:
    """``include_relations`` must accept a JSON-stringified list (regression
    for Claude Code stdio shim)."""
    mock_uow.tracks.get.return_value = None
    with pytest.raises(Exception, match="not found"):
        await stringified_mcp_client.call_tool(
            "entity_get",
            {
                "entity": "track",
                "id": 999,
                "include_relations": ["features", "artists"],
            },
        )


@pytest.mark.asyncio
async def test_entity_list_native_dict(mcp_client: Any, mock_uow: MagicMock) -> None:
    """``filters=`` must accept a native dict."""
    page = MagicMock()
    page.items = []
    page.total = 0
    page.next_cursor = None
    mock_uow.tracks.filter.return_value = page

    result = await mcp_client.call_tool(
        "entity_list",
        {"entity": "track", "filters": {"id__in": [1, 2, 3]}, "limit": 5},
    )
    data = result.structured_content or result.data
    assert data["entity"] == "track"
    assert data["items"] == []


@pytest.mark.asyncio
async def test_entity_list_stringified_dict(
    stringified_mcp_client: Any, mock_uow: MagicMock
) -> None:
    """``filters=`` must accept a JSON-stringified dict (regression for
    Claude Code stdio shim)."""
    page = MagicMock()
    page.items = []
    page.total = 0
    page.next_cursor = None
    mock_uow.tracks.filter.return_value = page

    result = await stringified_mcp_client.call_tool(
        "entity_list",
        {"entity": "track", "filters": {"id__in": [1, 2, 3]}, "limit": 5},
    )
    data = result.structured_content or result.data
    assert data["entity"] == "track"
    assert data["items"] == []
