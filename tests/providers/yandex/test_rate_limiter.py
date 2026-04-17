"""Rate limiter behavior tests."""

import time

import pytest

from app.providers.yandex.rate_limiter import TokenBucketRateLimiter


@pytest.mark.asyncio
async def test_no_delay_first_call() -> None:
    rl = TokenBucketRateLimiter(delay_s=0.5)
    t0 = time.monotonic()
    await rl.acquire()
    assert time.monotonic() - t0 < 0.05


@pytest.mark.asyncio
async def test_second_call_is_delayed() -> None:
    rl = TokenBucketRateLimiter(delay_s=0.2)
    await rl.acquire()
    t0 = time.monotonic()
    await rl.acquire()
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.18
    assert elapsed < 0.3


@pytest.mark.asyncio
async def test_backoff_after_429() -> None:
    rl = TokenBucketRateLimiter(delay_s=0.0, base_backoff_s=0.1, max_retries=3)
    assert rl.current_backoff() == 0.0
    await rl.on_rate_limited()
    assert rl.current_backoff() >= 0.1
    await rl.on_rate_limited()
    assert rl.current_backoff() >= 0.2


@pytest.mark.asyncio
async def test_backoff_resets_on_success() -> None:
    rl = TokenBucketRateLimiter(delay_s=0.0, base_backoff_s=0.1)
    await rl.on_rate_limited()
    await rl.on_rate_limited()
    assert rl.current_backoff() > 0
    rl.on_success()
    assert rl.current_backoff() == 0.0


@pytest.mark.asyncio
async def test_max_retries_exceeded() -> None:
    rl = TokenBucketRateLimiter(delay_s=0.0, max_retries=2)
    await rl.on_rate_limited()
    await rl.on_rate_limited()
    assert rl.retries_exhausted() is True
