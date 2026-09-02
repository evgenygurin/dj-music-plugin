"""Tests for ConcurrencyLimiterMiddleware."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.server.middleware.concurrency_limiter import ConcurrencyLimiterMiddleware


@pytest.fixture
def sem() -> AsyncIterator[ConcurrencyLimiterMiddleware]:
    yield ConcurrencyLimiterMiddleware(max_concurrency=3)


async def _fake_context(tool_name: str = "entity_create") -> Any:
    class FakeMessage:
        name = tool_name

    class FakeFctx:
        request_context = None
        fastmcp = None

        async def set_state(self, *a: Any, **kw: Any) -> None: ...

        async def delete_state(self, *a: Any, **kw: Any) -> None: ...

    ctx = MiddlewareContext(
        message=FakeMessage(),  # type: ignore[arg-type]
        fastmcp_context=FakeFctx(),  # type: ignore[arg-type]
    )
    return ctx


async def test_allows_readonly_tools_immediately() -> None:
    mw = ConcurrencyLimiterMiddleware(max_concurrency=1)

    async def call_next(_ctx: Any) -> str:
        return "done"

    # entity_get should NOT be limited
    ctx = await _fake_context("entity_get")
    result = await mw.on_call_tool(ctx, call_next)
    assert result == "done"


async def test_limits_concurrent_mutating_tools() -> None:
    mw = ConcurrencyLimiterMiddleware(max_concurrency=2)
    started: list[int] = []
    order: list[int] = []

    async def make_slow(i: int) -> None:
        async def call_next(_ctx: Any) -> None:
            started.append(i)
            await asyncio.sleep(0.05)
            order.append(i)

        ctx = await _fake_context("entity_create")
        await mw.on_call_tool(ctx, call_next)

    # Fire 3 slow calls — only 2 should run at once
    t1 = asyncio.create_task(make_slow(1))
    t2 = asyncio.create_task(make_slow(2))
    t3 = asyncio.create_task(make_slow(3))
    await asyncio.sleep(0.02)
    assert len(started) == 2, f"expected 2 started, got {started}"
    # Let the first two finish
    await asyncio.sleep(0.1)
    # Third should now start
    assert len(started) == 3, f"expected 3 started, got {started}"
    await asyncio.gather(t1, t2, t3)
    assert order == [1, 2, 3]


async def test_passthrough_unknown_tool_name() -> None:
    mw = ConcurrencyLimiterMiddleware(max_concurrency=1)

    async def call_next(_ctx: Any) -> str:
        return "passthrough"

    ctx = await _fake_context("some_other_tool")
    # Unknown tools are limited (not in _READ_ONLY_TOOLS)
    result = await mw.on_call_tool(ctx, call_next)
    assert result == "passthrough"
