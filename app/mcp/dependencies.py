"""FastMCP dependency injection factories.

All dependencies use Depends() — hidden from tool schemas.
DB session is cached per-request: multiple repos share one transaction.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp.server.dependencies import get_context
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.export import ExportRepository
from app.repositories.feature import FeatureRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository
from app.services.transition_cache import TransitionScoreCache


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


def get_transition_cache() -> TransitionScoreCache:
    """Get TransitionScoreCache from lifespan context.

    Returns:
        Configured TransitionScoreCache with storage backend from lifespan
    """
    ctx = get_context()
    storage = ctx.lifespan_context["transition_cache_store"]
    return TransitionScoreCache(
        storage=storage,
        ttl=settings.transition_cache_ttl,
    )
