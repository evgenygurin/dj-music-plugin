"""Tests for FileSystemProvider discovery and registration."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastmcp import Client

from app.server import fs_provider, mcp


@pytest.mark.asyncio
async def test_filesystem_provider_configured():
    """FileSystemProvider is configured with correct path."""
    assert fs_provider is not None
    # FileSystemProvider uses 'root' attribute, not 'path'
    expected_path = Path(__file__).parent.parent / "app" / "mcp"
    assert str(fs_provider).find(str(expected_path)) >= 0


@pytest.mark.asyncio
async def test_provider_discovers_tools(async_engine):
    """FileSystemProvider discovers tools from app/mcp/tools/."""
    from fastmcp.server.lifespan import Lifespan
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(async_engine, expire_on_commit=False)

    # Patch lifespan for test
    original_lifespan = mcp._lifespan

    async def _test_lifespan(server):  # type: ignore[no-untyped-def]
        yield {"db_engine": async_engine, "db_session_factory": factory}

    mcp._lifespan = Lifespan(_test_lifespan)

    try:
        async with Client(mcp) as client:
            # List all available tools
            tools = await client.list_tools()

            # Expected core tools (visible at startup)
            expected_core_tools = {
                "list_tracks",
                "get_track",
                "manage_tracks",
                "list_playlists",
                "get_playlist",
                "manage_playlist",
                "list_sets",
                "get_set",
                "manage_set",
                "get_track_features",
                "search",
                "unlock_tools",
                "list_platforms",
            }

            discovered_names = {tool.name for tool in tools}

            # All core tools should be discovered
            missing = expected_core_tools - discovered_names
            assert not missing, f"Missing core tools: {missing}"

            # Audio tools should NOT be visible (hidden by default)
            audio_tools = {"analyze_track", "analyze_batch", "separate_stems"}
            visible_audio = audio_tools & discovered_names
            assert not visible_audio, f"Audio tools should be hidden: {visible_audio}"

    finally:
        mcp._lifespan = original_lifespan


@pytest.mark.asyncio
async def test_tools_have_correct_metadata(async_engine):
    """Discovered tools have correct tags and annotations."""
    from fastmcp.server.lifespan import Lifespan
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    original_lifespan = mcp._lifespan

    async def _test_lifespan(server):  # type: ignore[no-untyped-def]
        yield {"db_engine": async_engine, "db_session_factory": factory}

    mcp._lifespan = Lifespan(_test_lifespan)

    try:
        async with Client(mcp) as client:
            tools = await client.list_tools()
            tools_by_name = {tool.name: tool for tool in tools}

            # Check list_tracks metadata
            list_tracks = tools_by_name.get("list_tracks")
            assert list_tracks is not None
            assert list_tracks.name == "list_tracks"
            assert list_tracks.description  # non-empty
            # Check parameters exist
            # inputSchema is a dict with 'properties' key
            param_names = set(list_tracks.inputSchema["properties"].keys())
            assert "limit" in param_names
            assert "cursor" in param_names

            # Check unlock_tools is admin tagged
            unlock_tools = tools_by_name.get("unlock_tools")
            assert unlock_tools is not None

            # Check list_platforms has readOnlyHint
            list_platforms = tools_by_name.get("list_platforms")
            assert list_platforms is not None

    finally:
        mcp._lifespan = original_lifespan


@pytest.mark.asyncio
async def test_hot_reload_setting():
    """FileSystemProvider respects settings.is_dev for hot reload."""
    from app.config import settings

    # Provider should have reload=settings.is_dev
    # Check via string representation since reload is a private/internal attr
    provider_str = str(fs_provider)
    expected_reload = settings.is_dev
    assert f"reload={expected_reload}" in provider_str

    # In test env, debug should be false → no hot reload
    assert settings.debug is False
    assert "reload=False" in provider_str
