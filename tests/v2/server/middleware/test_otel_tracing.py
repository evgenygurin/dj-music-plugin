from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.otel_tracing import OTELTracingMiddleware


def _ctx(tool: str = "entity_list") -> MiddlewareContext:
    msg = MagicMock()
    msg.name = tool
    return MiddlewareContext(message=msg, fastmcp_context=MagicMock())


@pytest.mark.asyncio
async def test_span_started_and_ended_on_success() -> None:
    span = MagicMock()

    class _SpanCM:
        def __enter__(self):
            return span

        def __exit__(self, *a):
            return False

    tracer = MagicMock()
    tracer.start_as_current_span = lambda name: _SpanCM()
    mw = OTELTracingMiddleware(tracer=tracer)
    call_next = AsyncMock(return_value="ok")
    await mw.on_call_tool(_ctx("entity_list"), call_next)
    span.set_attribute.assert_any_call("mcp.tool", "entity_list")


@pytest.mark.asyncio
async def test_span_records_exception() -> None:
    span = MagicMock()

    class _SpanCM:
        def __enter__(self):
            return span

        def __exit__(self, *a):
            return False

    tracer = MagicMock()
    tracer.start_as_current_span = lambda name: _SpanCM()
    mw = OTELTracingMiddleware(tracer=tracer)
    call_next = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        await mw.on_call_tool(_ctx(), call_next)
    span.record_exception.assert_called_once()


@pytest.mark.asyncio
async def test_noop_when_tracer_missing() -> None:
    mw = OTELTracingMiddleware(tracer=None)
    call_next = AsyncMock(return_value="ok")
    assert await mw.on_call_tool(_ctx(), call_next) == "ok"
