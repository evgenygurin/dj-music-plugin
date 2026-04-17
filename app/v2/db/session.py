"""Async engine + session factory.

The engine is constructed lazily via ``get_engine()`` so tests can
substitute their own URL without touching process-level state.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.v2.config import get_settings

_engine: AsyncEngine | None = None
_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the process-wide engine, constructing it on first call."""
    global _engine
    if _engine is None:
        s = get_settings().database
        kwargs: dict[str, object] = {"echo": s.db_echo}
        if "postgresql" in s.database_url:
            kwargs["pool_pre_ping"] = s.db_pool_pre_ping
            kwargs["pool_size"] = s.db_pool_size
            kwargs["connect_args"] = {"statement_cache_size": s.db_statement_cache_size}
        _engine = create_async_engine(s.database_url, **kwargs)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide session maker."""
    global _factory
    if _factory is None:
        _factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _factory


async def dispose() -> None:
    """Dispose the engine. Call in lifespan teardown."""
    global _engine, _factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _factory = None
