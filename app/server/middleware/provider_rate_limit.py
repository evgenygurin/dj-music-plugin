"""Rate-limit external provider calls (generalized YM rate limiter).

Matches by tool name prefix (e.g., ``provider_``). Adds a minimum delay
between calls across the whole MCP server instance (not per-session —
external APIs see a single IP).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.config import get_settings


class ProviderRateLimitMiddleware(Middleware):
    def __init__(
        self,
        *,
        delay_s: float | None = None,
        tool_prefixes: tuple[str, ...] = ("provider_",),
    ) -> None:
        if delay_s is None:
            delay_s = get_settings().yandex.rate_limit_delay
        self.delay_s = delay_s
        self.tool_prefixes = tool_prefixes
        self._last_call: float = 0.0
        self._lock = asyncio.Lock()

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        name = getattr(context.message, "name", "<unknown>")
        if not any(name.startswith(p) for p in self.tool_prefixes):
            return await call_next(context)
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self.delay_s:
                await asyncio.sleep(self.delay_s - elapsed)
            self._last_call = time.monotonic()
        return await call_next(context)
