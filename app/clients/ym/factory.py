"""Yandex Music client factory — shared by MCP lifespan and REST API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from app.clients.ym.client import YandexMusicClient


def build_ym_client() -> YandexMusicClient:
    """Create a configured Yandex Music client with rate limiting."""
    from app.clients.ym.client import YandexMusicClient
    from app.clients.ym.rate_limiter import RateLimiter

    rate_limiter = RateLimiter(
        delay=settings.ym_rate_limit_delay,
        max_retries=settings.ym_retry_attempts,
        backoff_factor=settings.ym_retry_backoff_factor,
    )
    return YandexMusicClient(
        token=settings.ym_token,
        user_id=settings.ym_user_id,
        base_url=settings.ym_base_url,
        rate_limiter=rate_limiter,
    )
