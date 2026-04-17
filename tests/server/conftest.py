"""Shared fixtures for v2 server tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import pytest_asyncio


@pytest.fixture(autouse=True)
def _reset_observability() -> AsyncIterator[None]:
    """Ensure ``bootstrap_observability()`` can run fresh each test."""
    import app.server.observability as obs

    if hasattr(obs, "_bootstrapped"):
        obs._bootstrapped = False
    yield
    if hasattr(obs, "_bootstrapped"):
        obs._bootstrapped = False


@pytest.fixture
def middleware_context_factory():
    """Return a factory that builds a minimal MiddlewareContext stub."""

    def _factory(
        *,
        tool_name: str = "entity_list",
        arguments: dict | None = None,
        readonly: bool = True,
        version: str | None = None,
        session_id: str = "sess-1",
    ):
        from fastmcp.server.middleware import MiddlewareContext

        mc = MiddlewareContext.__new__(MiddlewareContext)
        msg = MagicMock()
        msg.name = tool_name
        msg.arguments = arguments or {}
        mc.message = msg

        fctx = MagicMock()
        fctx.session_id = session_id
        fctx.client_id = "client-x"
        fctx.request_id = "req-x"
        fctx.state = {}

        tool = MagicMock()
        tool.annotations = SimpleNamespace(readOnlyHint=readonly)
        tool.version = version
        tool.meta = {}

        async def _get_tool(_name: str):
            return tool

        fctx.fastmcp.get_tool = _get_tool
        mc.fastmcp_context = fctx
        return mc

    return _factory


@pytest_asyncio.fixture
async def mcp_client():
    """In-memory FastMCP client against the real build_mcp_server()."""
    from fastmcp.client import Client

    from app.server.app import build_mcp_server

    mcp = build_mcp_server()
    async with Client(mcp) as c:
        yield c
