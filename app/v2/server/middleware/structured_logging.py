"""Innermost middleware — structured logs at tool boundary.

Runs closest to the handler. Emits enter/exit/error log records with
mcp_extra payload for downstream log pipelines to parse.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

log = logging.getLogger(__name__)


class StructuredLoggingMiddleware(Middleware):
    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        name = getattr(context.message, "name", "<unknown>")
        fctx = context.fastmcp_context
        session = getattr(fctx, "session_id", None) if fctx else None
        request = getattr(fctx, "request_id", None) if fctx else None
        extra = {
            "mcp_extra": {
                "tool": name,
                "session_id": session,
                "request_id": request,
            }
        }
        log.info("call_tool.enter", extra=extra)
        try:
            result = await call_next(context)
        except Exception as exc:
            log.exception(
                "call_tool.error",
                extra={
                    "mcp_extra": {
                        **extra["mcp_extra"],
                        "error": type(exc).__name__,
                    }
                },
            )
            raise
        log.info("call_tool.exit", extra=extra)
        return result
