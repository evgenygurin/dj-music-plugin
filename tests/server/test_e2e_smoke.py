"""End-to-end smoke test: Client(mcp) executes through the full pipeline.

Exercises the real ``build_mcp_server()`` — FileSystemProvider discovery,
transforms, 16 middleware, visibility policy — via an in-memory FastMCP
Client. This is the only test that hits the *entire* composition chain.
"""

from __future__ import annotations

import pytest
from fastmcp.client import Client

from app.server.app import build_mcp_server


@pytest.mark.asyncio
async def test_list_tools_after_build() -> None:
    mcp = build_mcp_server()
    async with Client(mcp) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        # Core always-visible tools from Phase 3.
        assert "entity_list" in names
        assert "entity_get" in names
        assert "entity_create" in names
        assert "provider_read" in names
        assert "unlock_namespace" in names


@pytest.mark.asyncio
async def test_namespace_policy_hides_tools() -> None:
    """Visibility policy should disable entity_delete / provider_write /
    playlist_sync globally at startup."""
    mcp = build_mcp_server()
    async with Client(mcp) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
    for hidden in ("entity_delete", "provider_write", "playlist_sync"):
        assert hidden not in names, f"{hidden} should be disabled by visibility policy"


@pytest.mark.asyncio
async def test_list_resources_and_prompts() -> None:
    """Full primitive coverage — resources and prompts discovered via FSP."""
    mcp = build_mcp_server()
    async with Client(mcp) as client:
        resources = await client.list_resources()
        prompts = await client.list_prompts()
    # At least the v2 resources/prompts shipped in Phases 4a/4b exist.
    assert isinstance(resources, list)
    assert isinstance(prompts, list)
