"""Shared fixtures for v2 tool integration tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport

# Import tool modules so their @tool decorators register.
# Phase 3 registers tools manually — FileSystemProvider wiring is Phase 5.


@pytest.fixture
def mock_uow() -> MagicMock:
    uow = MagicMock()
    # CRUD ops
    for attr in (
        "tracks",
        "playlists",
        "sets",
        "set_versions",
        "audio_files",
        "track_features",
        "transitions",
        "transition_history",
        "track_feedback",
        "track_affinity",
        "scoring_profiles",
    ):
        repo = MagicMock()
        repo.get = AsyncMock(return_value=None)
        repo.list = AsyncMock(return_value=MagicMock(items=[], next_cursor=None, total=0))
        repo.filter = AsyncMock(return_value=MagicMock(items=[], next_cursor=None, total=0))
        repo.count = AsyncMock(return_value=0)
        repo.create = AsyncMock(return_value=MagicMock(id=1))
        repo.update = AsyncMock(return_value=MagicMock(id=1))
        repo.delete = AsyncMock()
        repo.aggregate = AsyncMock(return_value=0)
        setattr(uow, attr, repo)
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    return uow


@pytest.fixture
def mock_provider_registry() -> MagicMock:
    r = MagicMock()
    provider = AsyncMock()
    provider.name = "yandex"
    provider.read.return_value = {"id": "1", "title": "Track"}
    provider.write.return_value = {"revision": 8}
    provider.search.return_value = {"tracks": {"results": [{"id": "1", "title": "X"}], "total": 1}}
    r.get.return_value = provider
    r.default.return_value = provider
    r.names.return_value = ["yandex"]
    return r


@pytest.fixture
async def mcp_server(
    mock_uow: MagicMock, mock_provider_registry: MagicMock
) -> AsyncIterator[FastMCP]:
    """FastMCP server with v2 tools registered + mocked DI."""
    from app.v2.registry.defaults import register_default_entities
    from app.v2.server import di

    # Register entities (safe to call in tests — idempotent at EntityRegistry level).
    register_default_entities()

    # Monkey-patch DI resolvers so tests don't need a real DB.
    di.get_uow = lambda: mock_uow  # type: ignore[attr-defined]
    di.get_provider_registry = lambda: mock_provider_registry  # type: ignore[attr-defined]

    mcp = FastMCP(name="dj-music-v2-test")

    # Register every v2 tool on this server.
    from app.v2.tools.admin import unlock_namespace as _un
    from app.v2.tools.compute import score_pool as _sp
    from app.v2.tools.compute import sequence_optimize as _so
    from app.v2.tools.entity import (
        aggregate as _agg,
    )
    from app.v2.tools.entity import (
        create as _cr,
    )
    from app.v2.tools.entity import (
        delete as _de,
    )
    from app.v2.tools.entity import (
        get as _ge,
    )
    from app.v2.tools.entity import (
        list as _li,
    )
    from app.v2.tools.entity import (
        update as _up,
    )
    from app.v2.tools.provider import read as _pr
    from app.v2.tools.provider import search as _ps
    from app.v2.tools.provider import write as _pw
    from app.v2.tools.sync import playlist_sync as _py

    for mod in (_li, _ge, _cr, _up, _de, _agg, _pr, _pw, _ps, _sp, _so, _py, _un):
        for name in dir(mod):
            obj = getattr(mod, name)
            if callable(obj) and getattr(obj, "__is_tool__", False):
                mcp.add_tool(obj)  # type: ignore[attr-defined]

    yield mcp


@pytest.fixture
async def mcp_client(mcp_server: FastMCP) -> AsyncIterator[Client]:
    async with Client(transport=FastMCPTransport(mcp_server)) as c:
        yield c
