from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.response_limit import ResponseLimitingMiddleware


def _ctx() -> MiddlewareContext:
    msg = MagicMock()
    msg.name = "entity_list"
    return MiddlewareContext(message=msg, fastmcp_context=None)


@pytest.mark.asyncio
async def test_passes_small_response_untouched() -> None:
    mw = ResponseLimitingMiddleware(max_bytes=50_000)
    payload = {"items": [1, 2, 3]}
    call_next = AsyncMock(return_value=payload)
    assert await mw.on_call_tool(_ctx(), call_next) is payload


@pytest.mark.asyncio
async def test_truncates_oversized_dict() -> None:
    mw = ResponseLimitingMiddleware(max_bytes=200)
    payload = {"items": ["x" * 50 for _ in range(100)]}
    call_next = AsyncMock(return_value=payload)
    result = await mw.on_call_tool(_ctx(), call_next)
    assert result.get("truncated") is True
    assert "limit_bytes" in result


@pytest.mark.asyncio
async def test_truncates_oversized_string() -> None:
    mw = ResponseLimitingMiddleware(max_bytes=100)
    call_next = AsyncMock(return_value="x" * 10_000)
    result = await mw.on_call_tool(_ctx(), call_next)
    assert isinstance(result, str)
    assert "truncated" in result
