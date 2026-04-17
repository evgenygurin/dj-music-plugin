"""Token-bucket rate limiter with exponential backoff on 429 responses.

Yandex Music API rate-limits aggressively on both reads and writes.
Default delay (1.5s) configurable via DJ_YM_RATE_LIMIT_DELAY.
"""

from __future__ import annotations

import asyncio
import time


class TokenBucketRateLimiter:
    """Enforces min delay between calls + exponential backoff on 429."""

    def __init__(
        self,
        *,
        delay_s: float = 1.5,
        base_backoff_s: float = 2.0,
        max_retries: int = 3,
    ) -> None:
        self._delay_s = delay_s
        self._base_backoff_s = base_backoff_s
        self._max_retries = max_retries
        self._last_call_at: float = 0.0
        self._retry_count: int = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until the next request is allowed."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call_at
            backoff = self.current_backoff()
            wait = max(0.0, max(self._delay_s, backoff) - elapsed)
            if self._last_call_at == 0.0 and backoff == 0.0:
                wait = 0.0
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call_at = time.monotonic()

    async def on_rate_limited(self) -> None:
        """Called after observing HTTP 429."""
        self._retry_count += 1

    def on_success(self) -> None:
        """Called after a successful response — reset backoff."""
        self._retry_count = 0

    def current_backoff(self) -> float:
        if self._retry_count == 0:
            return 0.0
        return self._base_backoff_s * (2 ** (self._retry_count - 1))

    def retries_exhausted(self) -> bool:
        return self._retry_count >= self._max_retries
