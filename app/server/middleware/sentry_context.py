"""Tag each tool call with MCP context on Sentry scope.

If ``sentry_sdk`` is not installed or not initialized, middleware is a no-op —
observability is optional.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

try:  # pragma: no cover - optional dependency
    import sentry_sdk as _sentry_default
except ImportError:  # pragma: no cover
    _sentry_default = None  # type: ignore[assignment]


class SentryContextMiddleware(Middleware):
    def __init__(self, *, sentry_module: Any | None = _sentry_default) -> None:
        self._sentry = sentry_module

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        if self._sentry is None:
            return await call_next(context)
        with self._sentry.push_scope() as scope:
            tool_name = getattr(context.message, "name", "<unknown>")
            scope.set_tag("mcp.tool", tool_name)
            fctx = getattr(context, "fastmcp_context", None)
            if fctx is not None:
                for attr in ("session_id", "client_id", "request_id"):
                    try:
                        value = getattr(fctx, attr, None)
                    except (RuntimeError, AttributeError):
                        # FastMCP v3 raises RuntimeError when these properties
                        # are accessed outside an active session (e.g. via REST).
                        value = None
                    scope.set_tag(f"mcp.{attr}", value)
            return await call_next(context)
