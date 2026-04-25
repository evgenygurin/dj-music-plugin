from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.server.middleware.cost_tracking import CostTrackingMiddleware

from .conftest import make_async_ctx


def _ctx(name: str) -> MiddlewareContext:
    return make_async_ctx(tool_name=name)


@pytest.mark.asyncio
async def test_records_provider_call_count() -> None:
    emitted: list[dict] = []
    mw = CostTrackingMiddleware(sink=emitted.append)
    ctx = _ctx("provider_read")

    async def call_next(c):
        c.fastmcp_context.state.setdefault("cost", {"provider_calls": 0, "llm_tokens": 0})
        c.fastmcp_context.state["cost"]["provider_calls"] += 3
        return "ok"

    await mw.on_call_tool(ctx, call_next)
    assert emitted[0]["provider_calls"] == 3
    assert emitted[0]["tool"] == "provider_read"


@pytest.mark.asyncio
async def test_records_llm_tokens() -> None:
    emitted: list[dict] = []
    mw = CostTrackingMiddleware(sink=emitted.append)
    ctx = _ctx("some_tool")

    async def call_next(c):
        c.fastmcp_context.state.setdefault("cost", {"provider_calls": 0, "llm_tokens": 0})
        c.fastmcp_context.state["cost"]["llm_tokens"] += 1500
        return "ok"

    await mw.on_call_tool(ctx, call_next)
    assert emitted[0]["llm_tokens"] == 1500


@pytest.mark.asyncio
async def test_records_zero_when_nothing_happened() -> None:
    emitted: list[dict] = []
    mw = CostTrackingMiddleware(sink=emitted.append)
    call_next = AsyncMock(return_value="ok")
    await mw.on_call_tool(_ctx("entity_list"), call_next)
    assert emitted[0] == {
        "tool": "entity_list",
        "provider_calls": 0,
        "llm_tokens": 0,
    }


@pytest.mark.asyncio
async def test_skips_when_session_unavailable() -> None:
    """REST/in-process callers have no MCP session.

    `fctx.set_state(...)` internally builds a key from `session_id` (a property
    that raises RuntimeError when there is no active session). The middleware
    must catch this and pass through to call_next without emitting cost tags;
    otherwise every tool call via REST returns 500.
    """
    emitted: list[dict] = []
    mw = CostTrackingMiddleware(sink=emitted.append)

    async def _raises(*_a: object, **_kw: object) -> None:
        raise RuntimeError("session_id is not available because no session exists")

    fctx = MagicMock()
    fctx.set_state = _raises
    fctx.get_state = _raises
    msg = MagicMock()
    msg.name = "entity_aggregate"
    ctx = MiddlewareContext(message=msg, fastmcp_context=fctx)

    call_next = AsyncMock(return_value="ok")
    result = await mw.on_call_tool(ctx, call_next)

    assert result == "ok"
    call_next.assert_awaited_once()
    assert emitted == []  # no sink event when no session
