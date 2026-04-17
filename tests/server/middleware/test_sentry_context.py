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
