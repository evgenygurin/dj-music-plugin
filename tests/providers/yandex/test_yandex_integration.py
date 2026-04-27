"""Integration round-trip tests against api.music.yandex.net.

Skipped automatically when ``DJ_YM_TOKEN`` is not set (CI without
secrets, contributor laptops without YM accounts). Covers the surfaces
where v1.0.10-v1.0.12 found output Union-narrowing bugs that the unit
test suite missed because it never round-tripped against a real provider.

Run live with::

    DJ_YM_TOKEN=... uv run pytest tests/providers/yandex/test_yandex_integration.py -v -m integration

Run skipped (default CI path)::

    uv run pytest tests/providers/yandex/test_yandex_integration.py -v
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from fastmcp import Client, FastMCP
from fastmcp.client.transports import FastMCPTransport

from app.server.app import build_mcp_server

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("DJ_YM_TOKEN"),
        reason="DJ_YM_TOKEN not set - integration tests against YM skipped",
    ),
]


@pytest.fixture
def mcp_with_yandex() -> FastMCP:
    """Full production server (no mocking) so the v1.1.0 middleware
    chain participates in the round-trip."""
    return build_mcp_server()


def _unwrap(result: Any) -> dict[str, Any]:
    return result.structured_content or result.data


@pytest.mark.asyncio
async def test_provider_search_round_trip(mcp_with_yandex: FastMCP) -> None:
    async with Client(transport=FastMCPTransport(mcp_with_yandex)) as client:
        result = await client.call_tool(
            "provider_search",
            {
                "provider": "yandex",
                "query": "Amelie Lens",
                "type": "tracks",
                "limit": 3,
            },
        )
        data = _unwrap(result)
        assert data["provider"] == "yandex"
        assert isinstance(data.get("items"), list)


@pytest.mark.asyncio
async def test_provider_read_likes_returns_dict(
    mcp_with_yandex: FastMCP,
) -> None:
    """Pins the wrapped-list response shape (v1.0.12 audit found this OK)."""
    async with Client(transport=FastMCPTransport(mcp_with_yandex)) as client:
        result = await client.call_tool("provider_read", {"provider": "yandex", "entity": "likes"})
        data = _unwrap(result)
        assert isinstance(data["data"], dict)
        assert "track_ids" in data["data"]


@pytest.mark.asyncio
async def test_provider_write_playlist_round_trip(
    mcp_with_yandex: FastMCP,
) -> None:
    """Create + delete throwaway playlist.

    Regression for v1.0.12: ``ProviderWriteResult.data`` previously
    rejected the bare-string ``"ok"`` that YM returns from playlist
    delete, crashing on response serialization despite the YM-side
    delete having already succeeded.
    """
    async with Client(transport=FastMCPTransport(mcp_with_yandex)) as client:
        created = await client.call_tool(
            "provider_write",
            {
                "provider": "yandex",
                "entity": "playlist",
                "operation": "create",
                "params": {"title": "__pytest_integration_throwaway__"},
            },
        )
        playlist_kind = _unwrap(created)["data"]["kind"]

        deleted = await client.call_tool(
            "provider_write",
            {
                "provider": "yandex",
                "entity": "playlist",
                "operation": "delete",
                "params": {"playlist_id": playlist_kind},
            },
        )
        assert _unwrap(deleted)["data"] == "ok"
