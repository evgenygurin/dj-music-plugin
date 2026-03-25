"""FastMCP dependency injection factories.

All dependencies use Depends() — hidden from tool schemas.
DB session is cached per-request: multiple repos share one transaction.

Key patterns:
- get_db_session() is an async context manager with auto-commit/rollback
- FastMCP's Depends() caches per-request → same session across all repos
- Repos ONLY flush, never commit (transaction boundary = tool boundary)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.server.dependencies import get_context
from sqlalchemy.ext.asyncio import AsyncSession

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
    """Scoped async DB session — auto-commit on success, rollback on error."""
    ctx = get_context()
    factory = ctx.lifespan_context["db_session_factory"]
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Repository factories ─────────────────────────────


def get_track_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TrackRepository:
    return TrackRepository(session)


def get_playlist_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlaylistRepository:
    return PlaylistRepository(session)


def get_set_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SetRepository:
    return SetRepository(session)


def get_feature_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FeatureRepository:
    return FeatureRepository(session)


def get_transition_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TransitionRepository:
    return TransitionRepository(session)


def get_export_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExportRepository:
    return ExportRepository(session)


# ── Lifespan context accessors ───────────────────────


def get_ym_client() -> YandexMusicClient:
    """Get YM client from lifespan context."""
    ctx = get_context()
    return ctx.lifespan_context["ym_client"]  # type: ignore[return-value]


def get_analyzer_registry():  # type: ignore[no-untyped-def]
    """Get analyzer registry from lifespan context."""
    ctx = get_context()
    return ctx.lifespan_context["analyzer_registry"]


def get_transition_cache() -> TransitionCache:
    """Get in-memory transition cache from lifespan context."""
    ctx = get_context()
    return ctx.lifespan_context["transition_cache"]  # type: ignore[return-value]
