from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import MiddlewareContext

from app.server.middleware.tool_timeout import ToolCallTimeoutMiddleware


def _ctx(name: str, timeout: float | None) -> MiddlewareContext:
    msg = MagicMock()
    msg.name = name
    fctx = MagicMock()
    tool = MagicMock()
    tool.meta = {"timeout_s": timeout} if timeout is not None else {}
    fctx.fastmcp.get_tool = AsyncMock(return_value=tool)
    return MiddlewareContext(message=msg, fastmcp_context=fctx)


@pytest.mark.asyncio
async def test_completes_within_timeout() -> None:
    mw = ToolCallTimeoutMiddleware(default_timeout=1.0)
    call_next = AsyncMock(return_value="ok")
    assert await mw.on_call_tool(_ctx("t", 1.0), call_next) == "ok"


@pytest.mark.asyncio
async def test_raises_on_overrun() -> None:
    mw = ToolCallTimeoutMiddleware(default_timeout=0.01)

    async def slow(_):
        await asyncio.sleep(1.0)
        return "never"

    with pytest.raises(ToolError, match="timed out"):
        await mw.on_call_tool(_ctx("slow", 0.01), slow)


@pytest.mark.asyncio
async def test_respects_per_tool_meta_over_default() -> None:
    mw = ToolCallTimeoutMiddleware(default_timeout=0.01)

    async def fifty_ms(_):
        await asyncio.sleep(0.05)
        return "ok"

    assert await mw.on_call_tool(_ctx("t", 0.5), fifty_ms) == "ok"
