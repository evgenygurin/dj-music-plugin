"""Lifespan management for the FastAPI wrapper."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.state import get_runtime
from app.config import settings
from app.ym.client import YandexMusicClient
from app.ym.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


def build_api_ym_client() -> YandexMusicClient:
    """Create the dedicated YM client used by the HTTP wrapper."""
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


def build_ym_client() -> YandexMusicClient:
    """Compatibility alias for tests and internal callers."""
    return build_api_ym_client()


@asynccontextmanager
async def api_lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Start the MCP lifespan and the dedicated HTTP YM client."""
    runtime = get_runtime(app)  # type: ignore[arg-type]
    runtime.ym_client = build_ym_client()

    try:
        async with runtime.mcp_app.router.lifespan_context(runtime.mcp_app):
            runtime.mcp_ready = True
            logger.info("MCP server started — tool execution enabled")
            yield
    except Exception:
        logger.exception(
            "MCP lifespan failed (DB unreachable?) — "
            "tool discovery works, but tool execution disabled"
        )
        runtime.mcp_ready = False
        yield
    finally:
        runtime.mcp_ready = False
        runtime.signed_url_cache.clear()
        if runtime.ym_client is not None:
            await runtime.ym_client.close()
            runtime.ym_client = None
