"""unlock_namespace tool metadata tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.context import Context

from app.tools.admin import unlock_namespace as _mod


def test_tool_module_has_expected_symbols() -> None:
    assert hasattr(_mod, "unlock_namespace")
    assert hasattr(_mod, "NAMESPACES")
    assert hasattr(_mod, "NAMESPACE_TAGS")


def test_known_namespaces() -> None:
    assert "all" in _mod.NAMESPACES
    assert "sync" in _mod.NAMESPACES
    assert "crud:destructive" in _mod.NAMESPACES
    assert "provider:write" in _mod.NAMESPACES


def _ctx() -> MagicMock:
    c = MagicMock(spec=Context)
    c.enable_components = AsyncMock()
    c.disable_components = AsyncMock()
    c.list_tools = AsyncMock(return_value=[])
    return c


@pytest.mark.asyncio
async def test_unlock_awaits_enable_components() -> None:
    """Regression: ``ctx.enable_components`` is async and must be awaited.

    Without ``await`` the coroutine is silently dropped and the namespace
    stays locked despite a 200 OK response.
    """
    ctx = _ctx()
    await _mod.unlock_namespace(namespace="provider:write", action="unlock", ctx=ctx)
    ctx.enable_components.assert_awaited_once_with(tags={"namespace:provider:write"})


@pytest.mark.asyncio
async def test_lock_awaits_disable_components() -> None:
    """Regression: ``ctx.disable_components`` must be awaited too."""
    ctx = _ctx()
    await _mod.unlock_namespace(namespace="provider:write", action="lock", ctx=ctx)
    ctx.disable_components.assert_awaited_once_with(tags={"namespace:provider:write"})
