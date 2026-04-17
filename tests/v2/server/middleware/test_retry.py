from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.retry import RetryMiddleware, TransientError


def _ctx() -> MiddlewareContext:
    msg = MagicMock()
    msg.name = "entity_list"
    return MiddlewareContext(message=msg, fastmcp_context=None)


@pytest.mark.asyncio
async def test_success_first_try_no_retry() -> None:
    mw = RetryMiddleware(max_retries=2, base_delay=0)
    call_next = AsyncMock(return_value="ok")
    assert await mw.on_call_tool(_ctx(), call_next) == "ok"
    assert call_next.await_count == 1


@pytest.mark.asyncio
async def test_retries_transient_error() -> None:
    mw = RetryMiddleware(max_retries=2, base_delay=0)
    call_next = AsyncMock(side_effect=[TransientError("fail1"), TransientError("fail2"), "ok"])
    assert await mw.on_call_tool(_ctx(), call_next) == "ok"
    assert call_next.await_count == 3


@pytest.mark.asyncio
async def test_gives_up_after_max() -> None:
    mw = RetryMiddleware(max_retries=2, base_delay=0)
    call_next = AsyncMock(side_effect=TransientError("always"))
    with pytest.raises(TransientError):
        await mw.on_call_tool(_ctx(), call_next)
    assert call_next.await_count == 3


@pytest.mark.asyncio
async def test_does_not_retry_non_transient() -> None:
    mw = RetryMiddleware(max_retries=5, base_delay=0)
    call_next = AsyncMock(side_effect=ValueError("bad input"))
    with pytest.raises(ValueError):
        await mw.on_call_tool(_ctx(), call_next)
    assert call_next.await_count == 1
