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


def get_set_service(
    set_repo=Depends(get_set_repo),  # noqa: B008
    track_repo=Depends(get_track_repo),  # noqa: B008
    playlist_repo=Depends(get_playlist_repo),  # noqa: B008
    feature_repo=Depends(get_feature_repo),  # noqa: B008
    transition_repo=Depends(get_transition_repo),  # noqa: B008
):  # type: ignore[no-untyped-def]
    from app.services.set_service import SetService

    return SetService(set_repo, track_repo, playlist_repo, feature_repo, transition_repo)


def get_search_service(
    track_repo=Depends(get_track_repo),  # noqa: B008
    playlist_repo=Depends(get_playlist_repo),  # noqa: B008
    set_repo=Depends(get_set_repo),  # noqa: B008
    feature_repo=Depends(get_feature_repo),  # noqa: B008
):  # type: ignore[no-untyped-def]
    from app.services.search_service import SearchService

    return SearchService(track_repo, playlist_repo, set_repo, feature_repo)


def get_curation_service(
    track_repo=Depends(get_track_repo),  # noqa: B008
    playlist_repo=Depends(get_playlist_repo),  # noqa: B008
    set_repo=Depends(get_set_repo),  # noqa: B008
    feature_repo=Depends(get_feature_repo),  # noqa: B008
    transition_repo=Depends(get_transition_repo),  # noqa: B008
):  # type: ignore[no-untyped-def]
    from app.services.curation_service import CurationService

    return CurationService(track_repo, playlist_repo, set_repo, feature_repo, transition_repo)


def get_reasoning_service(
    set_repo=Depends(get_set_repo),  # noqa: B008
    track_repo=Depends(get_track_repo),  # noqa: B008
    playlist_repo=Depends(get_playlist_repo),  # noqa: B008
    feature_repo=Depends(get_feature_repo),  # noqa: B008
    transition_repo=Depends(get_transition_repo),  # noqa: B008
):  # type: ignore[no-untyped-def]
    from app.services.reasoning_service import ReasoningService

    return ReasoningService(set_repo, track_repo, playlist_repo, feature_repo, transition_repo)


def get_delivery_service(
    set_repo=Depends(get_set_repo),  # noqa: B008
    track_repo=Depends(get_track_repo),  # noqa: B008
    feature_repo=Depends(get_feature_repo),  # noqa: B008
    transition_repo=Depends(get_transition_repo),  # noqa: B008
    export_repo=Depends(get_export_repo),  # noqa: B008
):  # type: ignore[no-untyped-def]
    from app.services.delivery_service import DeliveryService

    return DeliveryService(set_repo, track_repo, feature_repo, transition_repo, export_repo)


def get_sync_service(
    track_repo=Depends(get_track_repo),  # noqa: B008
    playlist_repo=Depends(get_playlist_repo),  # noqa: B008
    set_repo=Depends(get_set_repo),  # noqa: B008
    ym=Depends(get_ym_client),  # noqa: B008
):  # type: ignore[no-untyped-def]
    from app.services.sync_service import SyncService

    return SyncService(track_repo, playlist_repo, set_repo, ym)


def get_discovery_service(
    track_repo=Depends(get_track_repo),  # noqa: B008
    ym=Depends(get_ym_client),  # noqa: B008
):  # type: ignore[no-untyped-def]
    from app.services.discovery_service import DiscoveryService

    return DiscoveryService(track_repo, ym)


def get_metadata_service(
    session=Depends(get_db_session),  # noqa: B008
):  # type: ignore[no-untyped-def]
    from app.services.metadata_service import MetadataService

    return MetadataService(session)


def get_import_service(
    track_repo=Depends(get_track_repo),  # noqa: B008
    ym=Depends(get_ym_client),  # noqa: B008
    metadata=Depends(get_metadata_service),  # noqa: B008
):  # type: ignore[no-untyped-def]
    from app.services.import_service import ImportService

    return ImportService(track_repo, ym, metadata)


def get_audio_service(
    session=Depends(get_db_session),  # noqa: B008
    registry=Depends(get_analyzer_registry),  # noqa: B008
):  # type: ignore[no-untyped-def]
    """Get AudioService with DB session and analyzer registry."""
    from app.services.audio_service import AudioService

    return AudioService(session, registry)


def get_candidate_service(
    session=Depends(get_db_session),  # noqa: B008
):  # type: ignore[no-untyped-def]
    """Get CandidateService for transition candidate pruning."""
    from app.services.candidate_service import CandidateService

    return CandidateService(session)


def get_embedding_service(
    session=Depends(get_db_session),  # noqa: B008
):  # type: ignore[no-untyped-def]
    """Get EmbeddingService for vector embedding storage."""
    from app.services.embedding_service import EmbeddingService

    return EmbeddingService(session)
