"""Per-tool timing with pluggable recorder (metric emitter / log / Prometheus)."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

log = logging.getLogger(__name__)


def _default_recorder(name: str, duration_s: float, success: bool) -> None:
    log.info(
        "tool_timing",
        extra={
            "mcp_extra": {
                "tool": name,
                "duration_ms": round(duration_s * 1000, 2),
                "success": success,
            }
        },
    )


class DetailedTimingMiddleware(Middleware):
    def __init__(
        self,
        *,
        record: Callable[[str, float, bool], None] = _default_recorder,
    ) -> None:
        self._record = record

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        name = getattr(context.message, "name", "<unknown>")
        start = time.perf_counter()
        success = False
        try:
            result = await call_next(context)
            success = True
            return result
        finally:
            self._record(name, time.perf_counter() - start, success)
