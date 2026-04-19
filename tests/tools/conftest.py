"""Shared fixtures for v2 tool integration tests.

Uses ``build_mcp_app_for_tests`` from ``app.server.app`` so the full
FileSystemProvider tool discovery pipeline runs, but skips middleware,
visibility and lifespan — tests inject a mock UoW + ProviderRegistry by
monkey-patching the ``app.server.di`` resolvers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport


@pytest.fixture
def mock_uow() -> MagicMock:
    uow = MagicMock()
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
    r = MagicMock(spec=["get", "default", "names"])
    provider = MagicMock()
    provider.name = "yandex"
    provider.read = AsyncMock(return_value={"id": "1", "title": "Track"})
    provider.write = AsyncMock(return_value={"revision": 8})
    provider.search = AsyncMock(
        return_value={"tracks": {"results": [{"id": "1", "title": "X"}], "total": 1}}
    )
    r.get = MagicMock(return_value=provider)
    r.default = MagicMock(return_value=provider)
    r.names = MagicMock(return_value=["yandex"])
    return r


@pytest_asyncio.fixture
async def mcp_server(
    mock_uow: MagicMock,
    mock_provider_registry: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[FastMCP]:
    """FastMCP server via build_mcp_app_for_tests + mocked DI resolvers."""
    from app.registry.defaults import register_default_entities
    from app.registry.entity import EntityRegistry
    from app.server import di
    from app.server.app import build_mcp_app_for_tests

    EntityRegistry.clear()
    register_default_entities()

    # Tools bind Depends(get_uow) / Depends(get_provider_registry) at import
    # time — monkey-patching the module attribute doesn't affect those bound
    # references. Patch the low-level resolver instead.
    _slots = {
        "uow": mock_uow,
        "provider_registry": mock_provider_registry,
    }

    def _lookup(key: str, what: str):  # type: ignore[no-untyped-def]
        if key in _slots:
            return _slots[key]
        raise RuntimeError(f"{what} not initialized (test)")

    # `_read_slot` is async (reads via `await fctx.get_state(...)`);
    # `_read_lifespan` is sync (reads from `request_context.lifespan_context`).
    # Preserving the signatures matters — a mismatch surfaces as
    # `object MagicMock can't be used in 'await' expression`.
    async def _fake_read_slot(ctx, key, what):  # type: ignore[no-untyped-def]
        return _lookup(key, what)

    def _fake_read_lifespan(ctx, key, what):  # type: ignore[no-untyped-def]
        return _lookup(key, what)

    monkeypatch.setattr(di, "_read_slot", _fake_read_slot)
    monkeypatch.setattr(di, "_read_lifespan", _fake_read_lifespan)

    mcp = await build_mcp_app_for_tests(
        with_middleware=False,
        with_transforms=False,
        with_visibility=False,
        with_lifespan=False,
        with_sampling=False,
    )
    yield mcp


@pytest_asyncio.fixture
async def mcp_client(mcp_server: FastMCP) -> AsyncIterator[Client]:
    async with Client(transport=FastMCPTransport(mcp_server)) as c:
        yield c
