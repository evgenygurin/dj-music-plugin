"""FastMCP dependency injection factories.

All dependencies use Depends() — hidden from tool schemas.
DB session is cached per-request: multiple repos share one transaction.

Key patterns:
- get_db_session() returns AsyncSession via async context manager
- FastMCP's Depends() caches per-request → same session across all repos
- Commit happens in get_db_session finally block, not in tools/repos
- Repos ONLY flush, never commit (transaction boundary = tool boundary)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.server.dependencies import get_context
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.export import ExportRepository
from app.repositories.feature import FeatureRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository


@asynccontextmanager
async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Scoped async DB session — auto-commit on success, rollback on error.

    This is an async context manager that FastMCP's Depends() caches per-request.
    Multiple repos using Depends(get_db_session) receive the SAME session instance,
    guaranteeing a single transaction per tool call.

    Transaction lifecycle:
    1. Session created when first dependency requests it
    2. Session shared across all repos in the same tool call
    3. On success: commit
    4. On error: rollback

    Usage in tools:
        session: AsyncSession = Depends(get_db_session)

    Usage in repos:
        repo = TrackRepository(session=Depends(get_db_session))
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


def get_track_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TrackRepository:
    """TrackRepository with injected session.

    The session is injected via Depends(get_db_session) and cached per-request.
    Multiple calls to this dependency in the same tool call receive the same repo
    instance with the same session.
    """
    return TrackRepository(session)


def get_playlist_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlaylistRepository:
    """PlaylistRepository with injected session."""
    return PlaylistRepository(session)


def get_set_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SetRepository:
    """SetRepository with injected session."""
    return SetRepository(session)


def get_feature_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FeatureRepository:
    """FeatureRepository with injected session."""
    return FeatureRepository(session)


def get_transition_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TransitionRepository:
    """TransitionRepository with injected session."""
    return TransitionRepository(session)


def get_export_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExportRepository:
    """ExportRepository with injected session."""
    return ExportRepository(session)
