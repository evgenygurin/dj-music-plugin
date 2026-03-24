"""Tests for YM API rate limiter."""

from __future__ import annotations

import asyncio
import time

import pytest

from app.ym.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_acquire_respects_delay() -> None:
    """Second acquire should wait at least `delay` seconds."""
    limiter = RateLimiter(delay=0.2)

    await limiter.acquire()
    start = time.monotonic()
    await limiter.acquire()
    elapsed = time.monotonic() - start

    assert elapsed >= 0.18  # small tolerance


@pytest.mark.asyncio
async def test_acquire_no_wait_after_delay() -> None:
    """No wait needed when enough time has already passed."""
    limiter = RateLimiter(delay=0.1)

    await limiter.acquire()
    await asyncio.sleep(0.15)  # longer than delay

    start = time.monotonic()
    await limiter.acquire()
    elapsed = time.monotonic() - start

    assert elapsed < 0.05  # should be near-instant


@pytest.mark.asyncio
async def test_backoff_delay_exponential() -> None:
    """Backoff delay grows exponentially: delay * factor^attempt."""
    limiter = RateLimiter(delay=1.5, backoff_factor=2.0)

    assert limiter.get_backoff_delay(0) == pytest.approx(1.5)  # 1.5 * 2^0
    assert limiter.get_backoff_delay(1) == pytest.approx(3.0)  # 1.5 * 2^1
    assert limiter.get_backoff_delay(2) == pytest.approx(6.0)  # 1.5 * 2^2


@pytest.mark.asyncio
async def test_concurrent_acquires_serialized() -> None:
    """Concurrent acquires should be serialized with delay between each."""
    limiter = RateLimiter(delay=0.1)
    timestamps: list[float] = []

    async def acquire_and_record() -> None:
        await limiter.acquire()
        timestamps.append(time.monotonic())

    await asyncio.gather(*[acquire_and_record() for _ in range(4)])

    # Each consecutive acquire should be at least delay apart
    for i in range(1, len(timestamps)):
        gap = timestamps[i] - timestamps[i - 1]
        assert gap >= 0.08, f"Gap {i - 1}->{i} was {gap:.4f}s, expected >= 0.08s"
