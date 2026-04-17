"""Composed lifespans — Phase 3 contribution.

Phase 5 wires these together via FastMCP v3's lifespan composition with ``|``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from app.v2.config import get_settings
from app.v2.providers.yandex.adapter import YandexAdapter
from app.v2.providers.yandex.client import YandexClient
from app.v2.providers.yandex.rate_limiter import TokenBucketRateLimiter
from app.v2.registry.provider import ProviderRegistry


@asynccontextmanager
async def provider_lifespan() -> AsyncIterator[dict[str, Any]]:
    """Instantiate adapters and register them.

    Yields ``{"provider_registry": ProviderRegistry}`` merged into lifespan ctx.
    """
    settings = get_settings()
    registry = ProviderRegistry()

    yandex_client = YandexClient(
        token=settings.yandex.token,
        user_id=str(settings.yandex.user_id),
        base_url=settings.yandex.base_url,
        rate_limiter=TokenBucketRateLimiter(delay_s=settings.yandex.rate_limit_delay_s),
    )
    download_dir = Path(settings.yandex.library_path) if settings.yandex.library_path else None
    yandex_adapter = YandexAdapter(client=yandex_client, download_dir=download_dir)
    registry.register(yandex_adapter, default=True)

    try:
        yield {"provider_registry": registry}
    finally:
        await registry.close_all()
