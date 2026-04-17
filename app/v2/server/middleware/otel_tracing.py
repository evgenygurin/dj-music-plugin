"""OpenTelemetry span per tool call.

Uses ``tracer.start_as_current_span``. If no tracer is configured (OTEL not
installed or disabled) the middleware is a no-op.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

try:  # pragma: no cover
    from opentelemetry import trace as _otel_trace
    from opentelemetry.trace import Status, StatusCode

    _default_tracer = _otel_trace.get_tracer("app.v2.mcp")
except ImportError:  # pragma: no cover
    _default_tracer = None
    Status = None  # type: ignore[assignment,misc]
    StatusCode = None  # type: ignore[assignment,misc]


class OTELTracingMiddleware(Middleware):
    def __init__(self, *, tracer: Any | None = _default_tracer) -> None:
        self._tracer = tracer

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        if self._tracer is None:
            return await call_next(context)
        name = getattr(context.message, "name", "<unknown>")
        with self._tracer.start_as_current_span(f"mcp.tool.{name}") as span:
            span.set_attribute("mcp.tool", name)
            try:
                result = await call_next(context)
            except Exception as exc:
                span.record_exception(exc)
                if StatusCode is not None:
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise
            if StatusCode is not None:
                span.set_status(Status(StatusCode.OK))
            return result
