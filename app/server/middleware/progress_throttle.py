"""Throttle ``ctx.report_progress`` to at most N events per second.

Replaces ``fctx.report_progress`` with a wrapped async callable for the
duration of one tool call, then restores it. Drops messages that arrive
within the rate-limit window (final message of a tool call is NOT
guaranteed — callers that must land a final event should call
``ctx.info(...)`` instead).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext


class ProgressThrottleMiddleware(Middleware):
    def __init__(self, *, max_per_second: int = 1) -> None:
        self.min_interval = 1.0 / max_per_second

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        fctx = context.fastmcp_context
        if fctx is None:
            return await call_next(context)
        original = getattr(fctx, "report_progress", None)
        if original is None:
            return await call_next(context)

        last_emit = {"t": 0.0}

        async def throttled(
            progress: float,
            total: float | None = None,
            message: str | None = None,
        ) -> None:
            now = time.monotonic()
            if now - last_emit["t"] < self.min_interval:
                return
            last_emit["t"] = now
            await original(progress, total, message)

        fctx.report_progress = throttled  # type: ignore[method-assign]
        try:
            return await call_next(context)
        finally:
            fctx.report_progress = original  # type: ignore[method-assign]
