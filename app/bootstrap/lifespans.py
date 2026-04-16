"""FastMCP lifespan assembly helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastmcp.server.lifespan import lifespan
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.utils.cache import TransitionCache


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
async def provider_lifespan(server: Any) -> AsyncIterator[dict[str, Any]]:
    """Music provider registry lifecycle.

    Creates all configured providers (currently YM) and exposes them
    via ProviderRegistry. Legacy ``ym_client`` key preserved for
    backward compat during migration.
    """
    from app.clients.ym.adapter import YandexMusicAdapter
    from app.clients.ym.factory import build_ym_client
    from app.providers.registry import ProviderRegistry

    ym_client = build_ym_client()
    adapter = YandexMusicAdapter(ym_client)

    registry = ProviderRegistry()
    registry.register(adapter, default=True)

    try:
        yield {
            "provider_registry": registry,
            "ym_client": ym_client,
        }
    finally:
        await registry.close_all()


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
    return db_lifespan | provider_lifespan | analyzer_lifespan | cache_lifespan
