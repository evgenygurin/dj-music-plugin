from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.server.middleware.sentry_context import SentryContextMiddleware


def _ctx(tool_name: str = "entity_list", session_id: str = "sess-1") -> MiddlewareContext:
    msg = MagicMock()
    msg.name = tool_name
    fastmcp_ctx = MagicMock()
    fastmcp_ctx.session_id = session_id
    fastmcp_ctx.client_id = "client-x"
    fastmcp_ctx.request_id = "req-9"
    return MiddlewareContext(message=msg, fastmcp_context=fastmcp_ctx)


@pytest.mark.asyncio
async def test_sets_scope_tags_when_sdk_available() -> None:
    fake_scope = MagicMock()

    class _ScopeCM:
        def __enter__(self):
            return fake_scope

        def __exit__(self, *a):
            return False

    fake_sentry = MagicMock()
    fake_sentry.push_scope = lambda: _ScopeCM()

    mw = SentryContextMiddleware(sentry_module=fake_sentry)
    call_next = AsyncMock(return_value="ok")
    await mw.on_call_tool(_ctx(), call_next)
    fake_scope.set_tag.assert_any_call("mcp.tool", "entity_list")
    fake_scope.set_tag.assert_any_call("mcp.session_id", "sess-1")


@pytest.mark.asyncio
async def test_noop_when_sentry_missing() -> None:
    mw = SentryContextMiddleware(sentry_module=None)
    call_next = AsyncMock(return_value="ok")
    assert await mw.on_call_tool(_ctx(), call_next) == "ok"


def _stateless_ctx(tool_name: str = "entity_aggregate") -> MiddlewareContext:
    """Context where session_id/client_id/request_id raise RuntimeError.

    Mirrors fastmcp.Context behavior outside an active MCP session: the
    properties exist but raise instead of returning None, defeating
    getattr's default.
    """
    msg = MagicMock()
    msg.name = tool_name

    class _StatelessFCtx:
        @property
        def session_id(self) -> str:
            raise RuntimeError("session_id is not available because no session exists")

        @property
        def client_id(self) -> str:
            raise RuntimeError("client_id is not available because no session exists")

        @property
        def request_id(self) -> str:
            raise RuntimeError("request_id is not available because no session exists")

    return MiddlewareContext(message=msg, fastmcp_context=_StatelessFCtx())


@pytest.mark.asyncio
async def test_swallows_stateless_context_runtimeerror() -> None:
    """REST/in-process callers have a fastmcp_context whose id properties raise.

    Middleware must not let that bubble up — it should record None tags and
    call call_next normally. Otherwise every tool call via REST returns 500.
    Regression for sentry_context middleware after FastMCP v3 strict
    session_id property.
    """
    fake_scope = MagicMock()

    class _ScopeCM:
        def __enter__(self):
            return fake_scope

        def __exit__(self, *a):
            return False

    fake_sentry = MagicMock()
    fake_sentry.push_scope = lambda: _ScopeCM()

    mw = SentryContextMiddleware(sentry_module=fake_sentry)
    call_next = AsyncMock(return_value="ok")

    result = await mw.on_call_tool(_stateless_ctx(), call_next)

    assert result == "ok"
    call_next.assert_awaited_once()
    fake_scope.set_tag.assert_any_call("mcp.session_id", None)
    fake_scope.set_tag.assert_any_call("mcp.client_id", None)
    fake_scope.set_tag.assert_any_call("mcp.request_id", None)
