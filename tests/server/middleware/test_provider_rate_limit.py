from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.server.middleware.provider_rate_limit import (
    ProviderRateLimitMiddleware,
)


def _ctx(name: str) -> MiddlewareContext:
    msg = MagicMock()
    msg.name = name
    return MiddlewareContext(message=msg, fastmcp_context=MagicMock())


@pytest.mark.asyncio
async def test_spaces_consecutive_provider_calls() -> None:
    mw = ProviderRateLimitMiddleware(delay_s=0.05, tool_prefixes=("provider_",))
    call_next = AsyncMock(return_value="ok")
    t0 = time.monotonic()
    await mw.on_call_tool(_ctx("provider_read"), call_next)
    await mw.on_call_tool(_ctx("provider_read"), call_next)
    assert time.monotonic() - t0 >= 0.05


@pytest.mark.asyncio
async def test_does_not_throttle_local_tools() -> None:
    mw = ProviderRateLimitMiddleware(delay_s=1.0, tool_prefixes=("provider_",))
    call_next = AsyncMock(return_value="ok")
    t0 = time.monotonic()
    await mw.on_call_tool(_ctx("entity_list"), call_next)
    await mw.on_call_tool(_ctx("entity_get"), call_next)
    assert time.monotonic() - t0 < 0.5
