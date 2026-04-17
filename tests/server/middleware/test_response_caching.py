from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.server.middleware.response_caching import ResponseCachingMiddleware


def _ctx(name: str, readonly: bool, args: dict) -> MiddlewareContext:
    msg = MagicMock()
    msg.name = name
    msg.arguments = args
    fctx = MagicMock()
    tool = MagicMock()
    tool.annotations = MagicMock()
    tool.annotations.readOnlyHint = readonly
    fctx.fastmcp.get_tool = AsyncMock(return_value=tool)
    return MiddlewareContext(message=msg, fastmcp_context=fctx)


@pytest.mark.asyncio
async def test_caches_readonly_tool_result() -> None:
    mw = ResponseCachingMiddleware(ttl_seconds=60, max_entries=64)
    call_next = AsyncMock(return_value={"items": [1]})
    ctx = _ctx("entity_list", readonly=True, args={"q": "techno"})
    r1 = await mw.on_call_tool(ctx, call_next)
    r2 = await mw.on_call_tool(ctx, call_next)
    assert r1 == r2
    assert call_next.await_count == 1


@pytest.mark.asyncio
async def test_does_not_cache_mutations() -> None:
    mw = ResponseCachingMiddleware(ttl_seconds=60, max_entries=64)
    call_next = AsyncMock(return_value={"created": 1})
    ctx = _ctx("entity_create", readonly=False, args={"id": 1})
    await mw.on_call_tool(ctx, call_next)
    await mw.on_call_tool(ctx, call_next)
    assert call_next.await_count == 2


@pytest.mark.asyncio
async def test_different_args_different_cache_entries() -> None:
    mw = ResponseCachingMiddleware(ttl_seconds=60, max_entries=64)
    call_next = AsyncMock(side_effect=[{"a": 1}, {"b": 2}])
    ctx1 = _ctx("entity_list", True, {"q": "a"})
    ctx2 = _ctx("entity_list", True, {"q": "b"})
    assert (await mw.on_call_tool(ctx1, call_next)) == {"a": 1}
    assert (await mw.on_call_tool(ctx2, call_next)) == {"b": 2}


@pytest.mark.asyncio
async def test_ttl_expiry() -> None:
    mw = ResponseCachingMiddleware(ttl_seconds=0.01, max_entries=64)
    call_next = AsyncMock(side_effect=[{"n": 1}, {"n": 2}])
    ctx = _ctx("entity_list", True, {})
    assert (await mw.on_call_tool(ctx, call_next)) == {"n": 1}
    await asyncio.sleep(0.02)
    assert (await mw.on_call_tool(ctx, call_next)) == {"n": 2}
