from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.server.middleware.progress_throttle import ProgressThrottleMiddleware


def _make_ctx_with_report():
    calls: list[tuple[float, float]] = []

    async def original_report(
        progress: float, total: float | None = None, message: str | None = None
    ) -> None:
        calls.append((time.monotonic(), progress))

    fctx = MagicMock()
    fctx.report_progress = original_report
    msg = MagicMock()
    msg.name = "t"
    mc = MiddlewareContext(message=msg, fastmcp_context=fctx)
    return mc, calls, fctx


@pytest.mark.asyncio
async def test_throttles_rapid_progress_to_ratelimit() -> None:
    mw = ProgressThrottleMiddleware(max_per_second=1)
    ctx, calls, _ = _make_ctx_with_report()

    async def spam(c):
        for i in range(20):
            await c.fastmcp_context.report_progress(i, 20)
        return "ok"

    await mw.on_call_tool(ctx, spam)
    assert 1 <= len(calls) <= 3


@pytest.mark.asyncio
async def test_allows_spaced_progress() -> None:
    mw = ProgressThrottleMiddleware(max_per_second=10)
    ctx, calls, _ = _make_ctx_with_report()

    async def slow(c):
        for i in range(3):
            await c.fastmcp_context.report_progress(i, 3)
            await asyncio.sleep(0.11)
        return "ok"

    await mw.on_call_tool(ctx, slow)
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_restores_original_on_exit() -> None:
    mw = ProgressThrottleMiddleware(max_per_second=1)
    ctx, _, fctx = _make_ctx_with_report()
    original = fctx.report_progress
    await mw.on_call_tool(ctx, AsyncMock(return_value="ok"))
    assert fctx.report_progress is original
