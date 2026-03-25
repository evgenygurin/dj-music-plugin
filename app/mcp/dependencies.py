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


def get_track_repo(session=Depends(get_db_session)) -> TrackRepository:  # noqa: B008
    return TrackRepository(session)


def get_playlist_repo(session=Depends(get_db_session)) -> PlaylistRepository:  # noqa: B008
    return PlaylistRepository(session)


def get_set_repo(session=Depends(get_db_session)) -> SetRepository:  # noqa: B008
    return SetRepository(session)


def get_feature_repo(session=Depends(get_db_session)) -> FeatureRepository:  # noqa: B008
    return FeatureRepository(session)


def get_transition_repo(session=Depends(get_db_session)) -> TransitionRepository:  # noqa: B008
    return TransitionRepository(session)


def get_export_repo(session=Depends(get_db_session)) -> ExportRepository:  # noqa: B008
    return ExportRepository(session)


# ── Service factories ────────────────────────────────


def get_track_service(
    track_repo=Depends(get_track_repo),  # noqa: B008
    feature_repo=Depends(get_feature_repo),  # noqa: B008
):  # type: ignore[no-untyped-def]
    from app.services.track_service import TrackService

    return TrackService(track_repo, feature_repo)


def get_playlist_service(
    repo=Depends(get_playlist_repo),  # noqa: B008
):  # type: ignore[no-untyped-def]
    from app.services.playlist_service import PlaylistService

    return PlaylistService(repo)


# ── Lifespan context accessors ───────────────────────


def get_ym_client() -> YandexMusicClient:
    """Get YM client from lifespan context."""
    ctx = get_context()
    return ctx.lifespan_context["ym_client"]  # type: ignore[return-value]


def get_analyzer_registry():  # type: ignore[no-untyped-def]
    """Get analyzer registry from lifespan context."""
    ctx = get_context()
    return ctx.lifespan_context["analyzer_registry"]


def get_audio_service(
    session=Depends(get_db_session),  # noqa: B008
    registry=Depends(get_analyzer_registry),  # noqa: B008
):  # type: ignore[no-untyped-def]
    """Get AudioService with DB session and analyzer registry."""
    from app.services.audio_service import AudioService

    return AudioService(session, registry)


def get_transition_cache() -> TransitionCache:
    """Get in-memory transition cache from lifespan context."""
    ctx = get_context()
    return ctx.lifespan_context["transition_cache"]  # type: ignore[return-value]

