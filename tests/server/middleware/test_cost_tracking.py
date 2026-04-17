from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.server.middleware.cost_tracking import CostTrackingMiddleware


def _ctx(name: str) -> MiddlewareContext:
    msg = MagicMock()
    msg.name = name
    fctx = MagicMock()
    fctx.state = {}
    return MiddlewareContext(message=msg, fastmcp_context=fctx)


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
