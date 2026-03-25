"""FastMCP dependency injection factories.

All dependencies use Depends() — hidden from tool schemas.
DB session is cached per-request: multiple repos share one transaction.

Lifespan context access:
- DB: ctx.lifespan_context["db_engine"], ctx.lifespan_context["db_session_factory"]
- YM: ctx.lifespan_context["ym_client"]
- Audio: ctx.lifespan_context["analyzer_registry"]
- Cache: ctx.lifespan_context["transition_cache"]
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp.server.dependencies import get_context
from sqlalchemy.ext.asyncio import AsyncSession

from app.audio.registry import AnalyzerRegistry
from app.core.cache import TransitionCache
from app.repositories.export import ExportRepository
from app.repositories.feature import FeatureRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository
from app.ym.client import YandexMusicClient


@asynccontextmanager
async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Scoped async DB session — auto-commit on success, rollback on error.

    Cached per-request by FastMCP's Depends(). Multiple repos using
    Depends(get_db_session) receive the SAME session instance.
    """
    ctx = get_context()
    factory = ctx.lifespan_context["db_session_factory"]
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_track_repo(
    session: AsyncSession = None,  # type: ignore[assignment]
) -> TrackRepository:
    """TrackRepository with injected session."""
    if session is None:
        async with get_db_session() as session:
            return TrackRepository(session)
    return TrackRepository(session)


async def get_playlist_repo(
    session: AsyncSession = None,  # type: ignore[assignment]
) -> PlaylistRepository:
    if session is None:
        async with get_db_session() as session:
            return PlaylistRepository(session)
    return PlaylistRepository(session)


async def get_set_repo(
    session: AsyncSession = None,  # type: ignore[assignment]
) -> SetRepository:
    if session is None:
        async with get_db_session() as session:
            return SetRepository(session)
    return SetRepository(session)


async def get_feature_repo(
    session: AsyncSession = None,  # type: ignore[assignment]
) -> FeatureRepository:
    if session is None:
        async with get_db_session() as session:
            return FeatureRepository(session)
    return FeatureRepository(session)


async def get_transition_repo(
    session: AsyncSession = None,  # type: ignore[assignment]
) -> TransitionRepository:
    if session is None:
        async with get_db_session() as session:
            return TransitionRepository(session)
    return TransitionRepository(session)


async def get_export_repo(
    session: AsyncSession = None,  # type: ignore[assignment]
) -> ExportRepository:
    if session is None:
        async with get_db_session() as session:
            return ExportRepository(session)
    return ExportRepository(session)


# ── Lifespan context dependencies ─────────────────────


def get_ym_client() -> YandexMusicClient:
    """Get YM client from lifespan context.

    Accessible via Depends(get_ym_client) in tools.
    """
    ctx = get_context()
    client: YandexMusicClient = ctx.lifespan_context["ym_client"]
    return client


def get_analyzer_registry() -> AnalyzerRegistry:
    """Get analyzer registry from lifespan context.

    Accessible via Depends(get_analyzer_registry) in tools.
    """
    ctx = get_context()
    registry: AnalyzerRegistry = ctx.lifespan_context["analyzer_registry"]
    return registry


def get_transition_cache() -> TransitionCache:
    """Get transition cache from lifespan context.

    Accessible via Depends(get_transition_cache) in tools.
    """
    ctx = get_context()
    cache: TransitionCache = ctx.lifespan_context["transition_cache"]
    return cache
