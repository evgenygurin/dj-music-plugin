"""FastMCP lifespan assembly helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastmcp.server.lifespan import lifespan
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.utils.cache import TransitionCache
from app.engines.lifespan import audio_lifespan


def build_db_session_factory() -> tuple[Any, async_sessionmaker[AsyncSession]]:
    """Create the production database engine and session factory."""
    connect_args: dict[str, Any] = {}
    if settings.database_url.startswith("postgresql"):
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0

    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


def build_ym_client() -> Any:
    """Create a configured Yandex Music client."""
    from app.ym.client import YandexMusicClient
    from app.ym.rate_limiter import RateLimiter

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


@lifespan
async def db_lifespan(server: Any) -> AsyncIterator[dict[str, Any]]:
    """Database engine + session factory lifecycle."""
    engine, session_factory = build_db_session_factory()

    from app.db.seed import seed_reference_data

    await seed_reference_data(session_factory)

    try:
        yield {"db_engine": engine, "db_session_factory": session_factory}
    finally:
        await engine.dispose()


@lifespan
async def ym_lifespan(server: Any) -> AsyncIterator[dict[str, Any]]:
    """Yandex Music client lifecycle with rate limiting."""
    client = build_ym_client()
    try:
        yield {"ym_client": client}
    finally:
        await client.close()


@lifespan
async def analyzer_lifespan(server: Any) -> AsyncIterator[dict[str, Any]]:
    """Audio analyzer registry lifecycle."""
    from app.audio.analyzers import AnalyzerRegistry

    registry = AnalyzerRegistry()
    registry.discover()
    yield {"analyzer_registry": registry}


@lifespan
async def cache_lifespan(server: Any) -> AsyncIterator[dict[str, Any]]:
    """Cache lifecycle — transition scores + storage backends."""
    transition_cache = TransitionCache(
        max_size=settings.transition_cache_max_size,
        ttl=settings.transition_cache_ttl,
    )
    try:
        yield {"transition_cache": transition_cache}
    finally:
        transition_cache.clear()


def build_server_lifespan() -> Any:
    """Compose the production server lifespan."""
    return db_lifespan | ym_lifespan | analyzer_lifespan | cache_lifespan | audio_lifespan
