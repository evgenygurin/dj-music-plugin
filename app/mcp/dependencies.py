"""FastMCP dependency injection factories.

All dependencies use Depends() — hidden from tool schemas.
DB session is cached per-request: multiple repos share one transaction.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp.server.context import Context
from fastmcp.server.dependencies import Depends, get_context
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.export import ExportRepository
from app.repositories.feature import FeatureRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository


async def get_db_session() -> AsyncSession:
    """Scoped async DB session — retrieved from lifespan context.

    Cached per-request by FastMCP's Depends(). Multiple repos using
    Depends(get_db_session) receive the SAME session instance.

    Transaction lifecycle (commit/rollback) is managed at the tool boundary
    by the calling tool's context manager or by FastMCP infrastructure.
    """
    ctx: Context = get_context()
    factory = ctx.lifespan_context["db_session_factory"]
    async with factory() as session:
        yield session
        # Commit handled by tool-level wrapper or middleware
        await session.commit()


async def get_track_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)]
) -> TrackRepository:
    """TrackRepository with injected session."""
    return TrackRepository(session)


async def get_playlist_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)]
) -> PlaylistRepository:
    """PlaylistRepository with injected session."""
    return PlaylistRepository(session)


async def get_set_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)]
) -> SetRepository:
    """SetRepository with injected session."""
    return SetRepository(session)


async def get_feature_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)]
) -> FeatureRepository:
    """FeatureRepository with injected session."""
    return FeatureRepository(session)


async def get_transition_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)]
) -> TransitionRepository:
    """TransitionRepository with injected session."""
    return TransitionRepository(session)


async def get_export_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)]
) -> ExportRepository:
    """ExportRepository with injected session."""
    return ExportRepository(session)
