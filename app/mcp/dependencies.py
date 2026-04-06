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

from app.audio.analyzers import AnalyzerRegistry
from app.audio.timeseries import TimeseriesStorage
from app.core.cache import TransitionCache
from app.repositories.audio import AudioRepository
from app.repositories.candidate import CandidateRepository
from app.repositories.embedding import EmbeddingRepository
from app.repositories.export import ExportRepository
from app.repositories.feature import FeatureRepository
from app.repositories.ingestion import IngestionRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository
from app.services.audio_service import AudioService
from app.services.candidate_service import CandidateService
from app.services.curation_service import CurationService
from app.services.delivery_service import DeliveryService
from app.services.discovery_service import DiscoveryService
from app.services.embedding_service import EmbeddingService
from app.services.import_service import ImportService
from app.services.metadata_service import MetadataService
from app.services.playlist_service import PlaylistService
from app.services.reasoning_service import ReasoningService
from app.services.search_service import SearchService
from app.services.set_service import SetService
from app.services.sync_service import SyncService
from app.services.tiered_pipeline import TieredPipeline
from app.services.track_service import TrackService
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


def get_track_repo(session: AsyncSession = Depends(get_db_session)) -> TrackRepository:  # noqa: B008
    return TrackRepository(session)


def get_playlist_repo(session: AsyncSession = Depends(get_db_session)) -> PlaylistRepository:  # noqa: B008
    return PlaylistRepository(session)


def get_set_repo(session: AsyncSession = Depends(get_db_session)) -> SetRepository:  # noqa: B008
    return SetRepository(session)


def get_feature_repo(session: AsyncSession = Depends(get_db_session)) -> FeatureRepository:  # noqa: B008
    return FeatureRepository(session)


def get_transition_repo(session: AsyncSession = Depends(get_db_session)) -> TransitionRepository:  # noqa: B008
    return TransitionRepository(session)


def get_export_repo(session: AsyncSession = Depends(get_db_session)) -> ExportRepository:  # noqa: B008
    return ExportRepository(session)


def get_ingestion_repo(session: AsyncSession = Depends(get_db_session)) -> IngestionRepository:  # noqa: B008
    return IngestionRepository(session)


def get_audio_repo(session: AsyncSession = Depends(get_db_session)) -> AudioRepository:  # noqa: B008
    return AudioRepository(session)


def get_embedding_repo(session: AsyncSession = Depends(get_db_session)) -> EmbeddingRepository:  # noqa: B008
    return EmbeddingRepository(session)


def get_candidate_repo(session: AsyncSession = Depends(get_db_session)) -> CandidateRepository:  # noqa: B008
    return CandidateRepository(session)


# ── Lifespan context accessors ───────────────────────


def get_ym_client() -> YandexMusicClient:
    """Get YM client from lifespan context."""
    ctx = get_context()
    client: YandexMusicClient = ctx.lifespan_context["ym_client"]
    return client


def get_analyzer_registry() -> AnalyzerRegistry:
    """Get analyzer registry from lifespan context."""
    ctx = get_context()
    result: AnalyzerRegistry = ctx.lifespan_context["analyzer_registry"]
    return result


def get_transition_cache() -> TransitionCache:
    """Get in-memory transition cache from lifespan context."""
    ctx = get_context()
    cache: TransitionCache = ctx.lifespan_context["transition_cache"]
    return cache


# ── Service factories ────────────────────────────────


def get_track_service(
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    feature_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
) -> TrackService:
    return TrackService(track_repo, feature_repo)


def get_playlist_service(
    repo: PlaylistRepository = Depends(get_playlist_repo),  # noqa: B008
) -> PlaylistService:
    return PlaylistService(repo)


def get_set_service(
    set_repo: SetRepository = Depends(get_set_repo),  # noqa: B008
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    playlist_repo: PlaylistRepository = Depends(get_playlist_repo),  # noqa: B008
    feature_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
    transition_repo: TransitionRepository = Depends(get_transition_repo),  # noqa: B008
) -> SetService:
    return SetService(set_repo, track_repo, playlist_repo, feature_repo, transition_repo)


def get_search_service(
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    playlist_repo: PlaylistRepository = Depends(get_playlist_repo),  # noqa: B008
    set_repo: SetRepository = Depends(get_set_repo),  # noqa: B008
    feature_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
) -> SearchService:
    return SearchService(track_repo, playlist_repo, set_repo, feature_repo)


def get_curation_service(
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    playlist_repo: PlaylistRepository = Depends(get_playlist_repo),  # noqa: B008
    set_repo: SetRepository = Depends(get_set_repo),  # noqa: B008
    feature_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
    transition_repo: TransitionRepository = Depends(get_transition_repo),  # noqa: B008
) -> CurationService:
    return CurationService(track_repo, playlist_repo, set_repo, feature_repo, transition_repo)


def get_reasoning_service(
    set_repo: SetRepository = Depends(get_set_repo),  # noqa: B008
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    playlist_repo: PlaylistRepository = Depends(get_playlist_repo),  # noqa: B008
    feature_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
    transition_repo: TransitionRepository = Depends(get_transition_repo),  # noqa: B008
) -> ReasoningService:
    return ReasoningService(set_repo, track_repo, playlist_repo, feature_repo, transition_repo)


def get_delivery_service(
    set_repo: SetRepository = Depends(get_set_repo),  # noqa: B008
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    feature_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
    transition_repo: TransitionRepository = Depends(get_transition_repo),  # noqa: B008
    export_repo: ExportRepository = Depends(get_export_repo),  # noqa: B008
) -> DeliveryService:
    return DeliveryService(set_repo, track_repo, feature_repo, transition_repo, export_repo)


def get_sync_service(
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    playlist_repo: PlaylistRepository = Depends(get_playlist_repo),  # noqa: B008
    set_repo: SetRepository = Depends(get_set_repo),  # noqa: B008
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
) -> SyncService:
    return SyncService(track_repo, playlist_repo, set_repo, ym)


def get_discovery_service(
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
) -> DiscoveryService:
    return DiscoveryService(track_repo, ym)


def get_metadata_service(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> MetadataService:
    return MetadataService(session)


def get_import_service(
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    metadata: MetadataService = Depends(get_metadata_service),  # noqa: B008
    ingestion_repo: IngestionRepository = Depends(get_ingestion_repo),  # noqa: B008
) -> ImportService:
    return ImportService(track_repo, ym, metadata, ingestion_repo)


def get_audio_service(
    repo: AudioRepository = Depends(get_audio_repo),  # noqa: B008
    registry: AnalyzerRegistry = Depends(get_analyzer_registry),  # noqa: B008
) -> AudioService:
    """Get AudioService with repository and analyzer registry."""
    return AudioService(repo, registry)


def get_candidate_service(
    repo: CandidateRepository = Depends(get_candidate_repo),  # noqa: B008
) -> CandidateService:
    """Get CandidateService for transition candidate pruning."""
    return CandidateService(repo)


def get_embedding_service(
    repo: EmbeddingRepository = Depends(get_embedding_repo),  # noqa: B008
) -> EmbeddingService:
    """Get EmbeddingService for vector embedding storage."""
    return EmbeddingService(repo)


def get_timeseries_storage() -> TimeseriesStorage:
    """Get TimeseriesStorage for frame-level audio data."""
    return TimeseriesStorage()


def get_tiered_pipeline(
    audio_repo: AudioRepository = Depends(get_audio_repo),  # noqa: B008
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    registry: AnalyzerRegistry = Depends(get_analyzer_registry),  # noqa: B008
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    timeseries: TimeseriesStorage = Depends(get_timeseries_storage),  # noqa: B008
) -> TieredPipeline:
    """Get TieredPipeline for level-aware audio analysis."""
    from app.audio.pipeline import AnalysisPipeline

    pipeline = AnalysisPipeline(registry)
    return TieredPipeline(audio_repo, track_repo, pipeline, ym, timeseries=timeseries)
