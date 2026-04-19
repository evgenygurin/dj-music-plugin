from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.server.middleware.sampling_budget import (
    SamplingBudgetExceeded,
    SamplingBudgetMiddleware,
)

from .conftest import make_async_ctx


def _ctx(session_id: str = "s1") -> MiddlewareContext:
    mc = make_async_ctx(tool_name="x")
    mc.fastmcp_context.session_id = session_id
    return mc


@pytest.mark.asyncio
async def test_allows_until_budget() -> None:
    mw = SamplingBudgetMiddleware(max_samples_per_session=2)
    ctx = _ctx("s1")

    async def bump_twice(c):
        mw.note_sample(c)
        mw.note_sample(c)
        return "ok"

    await mw.on_call_tool(ctx, bump_twice)


@pytest.mark.asyncio
async def test_raises_over_budget() -> None:
    mw = SamplingBudgetMiddleware(max_samples_per_session=1)
    ctx = _ctx("s2")

    async def bump_over(c):
        mw.note_sample(c)
        mw.note_sample(c)
        return "ok"

    with pytest.raises(SamplingBudgetExceeded):
        await mw.on_call_tool(ctx, bump_over)


@pytest.mark.asyncio
async def test_budget_is_per_session() -> None:
    mw = SamplingBudgetMiddleware(max_samples_per_session=1)

    async def bump_one(c):
        mw.note_sample(c)
        return "ok"

    await mw.on_call_tool(_ctx("A"), bump_one)
    await mw.on_call_tool(_ctx("B"), bump_one)


@pytest.mark.asyncio
async def test_attaches_self_to_state() -> None:
    mw = SamplingBudgetMiddleware(max_samples_per_session=5)
    ctx = _ctx("s3")
    call_next = AsyncMock(return_value="ok")
    await mw.on_call_tool(ctx, call_next)
    assert ctx.fastmcp_context.state["sampling_budget"] is mw
