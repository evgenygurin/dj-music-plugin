"""Token bucket rate limiter with exponential backoff for YM API."""

from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Token bucket rate limiter with exponential backoff for YM API.

    Ensures minimum delay between requests and provides exponential
    backoff calculation for retry logic on HTTP 429 responses.
    """

    def __init__(
        self,
        delay: float = 1.5,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ) -> None:
        self._delay = delay
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._last_request: float = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request slot is available."""
        async with self._lock:
            now = time.monotonic()
            wait = self._delay - (now - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()

    def get_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay for retry attempt."""
        return self._delay * (self._backoff_factor**attempt)

    @property
    def max_retries(self) -> int:
        return self._max_retries
