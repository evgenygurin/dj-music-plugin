from __future__ import annotations

import contextlib
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


def test_used_dict_bounded() -> None:
    """``_used`` must not grow unbounded.

    Each MCP session creates a new bucket; over the lifetime of a long-
    running server that easily reaches tens of thousands of sessions and
    leaks a bucket per session. Bound the structure with an LRU-like
    cap (default 1024) so memory use stays flat.
    """
    mw = SamplingBudgetMiddleware(max_samples_per_session=1)

    class _StatefulCtx:
        def __init__(self, sid: str) -> None:
            self.session_id = sid
            self.fastmcp_context = self

    for i in range(2000):
        ctx = _StatefulCtx(f"sess-{i}")
        with contextlib.suppress(SamplingBudgetExceeded):
            mw.note_sample(ctx)

    # Pick whichever attribute the implementation uses internally.
    size = len(mw._used)
    assert size <= 1024, f"_used grew unbounded: {size} entries"


def test_stateless_global_cap_distinct_from_per_session() -> None:
    """Stateless callers must NOT defeat per-session limits.

    Old behaviour bucketed every stateless call under ``"__global__"``,
    so once a single per-session cap (default 10) was hit, all future
    stateless calls failed forever. Apply a SEPARATE cap for the
    stateless bucket from ``MCPSettings.sampling_global_cap``.
    """
    from app.config import get_settings

    global_cap = get_settings().mcp.sampling_global_cap
    assert isinstance(global_cap, int) and global_cap > 0

    # Use a tiny per-session cap to prove the stateless bucket is NOT
    # constrained by it (would raise after 1 call if the dict were
    # shared with a global per-session cap).
    mw = SamplingBudgetMiddleware(max_samples_per_session=1)

    class _StatelessCtx:
        @property
        def session_id(self):
            raise RuntimeError("session_id is not available because no session exists")

        @property
        def fastmcp_context(self):
            return self

    ctx = _StatelessCtx()

    # Should be able to do `global_cap` stateless samples; the
    # `global_cap+1`-th must raise.
    for _ in range(global_cap):
        mw.note_sample(ctx)

    with pytest.raises(SamplingBudgetExceeded):
        mw.note_sample(ctx)


@pytest.mark.asyncio
async def test_passthrough_when_session_unavailable() -> None:
    """REST/in-process: set_state raises RuntimeError; middleware must not 500.

    Cap-enforcement is best-effort observability; if there is no session we
    cannot scope a budget anyway. Pass through to call_next.
    """
    from unittest.mock import MagicMock

    async def _raises(*_a: object, **_kw: object) -> None:
        raise RuntimeError("session_id is not available because no session exists")

    state_dict: dict = {}
    fctx = MagicMock()
    fctx.state = state_dict
    fctx.set_state = _raises
    msg = MagicMock()
    msg.name = "entity_aggregate"
    mc = MiddlewareContext(message=msg, fastmcp_context=fctx)

    mw = SamplingBudgetMiddleware(max_samples_per_session=5)
    call_next = AsyncMock(return_value="ok")
    result = await mw.on_call_tool(mc, call_next)
    assert result == "ok"
    call_next.assert_awaited_once()
