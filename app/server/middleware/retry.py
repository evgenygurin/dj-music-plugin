"""Retry transient errors with exponential backoff.

TransientError is a marker — raise it from providers / DB layer when a
call is safe to retry. Non-transient exceptions propagate immediately.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

log = logging.getLogger(__name__)


class TransientError(Exception):
    """Marker for errors safe to retry."""


class RetryMiddleware(Middleware):
    def __init__(
        self,
        *,
        max_retries: int = 2,
        base_delay: float = 0.5,
        backoff_factor: float = 2.0,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        attempt = 0
        while True:
            try:
                return await call_next(context)
            except TransientError as exc:
                if attempt >= self.max_retries:
                    raise
                delay = self.base_delay * (self.backoff_factor**attempt)
                log.warning(
                    "retry attempt=%d delay=%.2fs error=%s",
                    attempt + 1,
                    delay,
                    exc,
                )
                if delay > 0:
                    await asyncio.sleep(delay)
                attempt += 1
