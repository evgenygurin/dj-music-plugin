"""Partial back-compat shim — RetryMiddleware class retained until Task 12.

Historically this file owned both ``RetryMiddleware`` and ``TransientError``.
As of v1.0.4 (Task 3):

- ``TransientError`` is re-exported from ``app.shared.errors`` (canonical).
- ``RetryMiddleware`` remains here until Task 12 rewires
  ``app/server/middleware/__init__.py`` to import the built-in
  ``fastmcp.server.middleware.error_handling.RetryMiddleware``.

Task 12 then deletes both this module and
``tests/server/middleware/test_retry.py``. Do not remove the
``RetryMiddleware`` class earlier — ``ALL_MIDDLEWARE`` still imports it.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.shared.errors import TransientError

log = logging.getLogger(__name__)


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


__all__ = ["RetryMiddleware", "TransientError"]
