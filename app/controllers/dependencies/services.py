"""Service and workflow dependency factories."""

from __future__ import annotations

from fastmcp.dependencies import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies.audio import get_audio_service, get_tiered_pipeline
from app.controllers.dependencies.db import get_db_session
from app.controllers.dependencies.external import get_ym_client
from app.controllers.dependencies.repos import (
    get_candidate_repo,
    get_embedding_repo,
    get_export_repo,
    get_feature_repo,
    get_ingestion_repo,
    get_playlist_repo,
    get_set_repo,
    get_track_repo,
    get_transition_history_repo,
    get_transition_repo,
)
from app.db.repositories.candidate import CandidateRepository
from app.db.repositories.embedding import EmbeddingRepository
from app.db.repositories.export import ExportRepository
from app.db.repositories.feature import FeatureRepository
from app.db.repositories.ingestion import IngestionRepository
from app.db.repositories.playlist import PlaylistRepository
from app.db.repositories.set import SetRepository
from app.db.repositories.track import TrackRepository
from app.db.repositories.transition import TransitionRepository
from app.db.repositories.transition_history import TransitionHistoryRepository
from app.services.audio_service import AudioService
from app.services.candidate_service import CandidateService
from app.services.curation.facade import CurationService
from app.services.delivery_service import DeliveryService
from app.services.discovery_service import DiscoveryService
from app.services.embedding_service import EmbeddingService
from app.services.import_service import ImportService
from app.services.metadata_service import MetadataService
from app.services.playlist_service import PlaylistService
from app.services.reasoning_service import ReasoningService
from app.services.search_service import SearchService
from app.services.set.facade import SetService
from app.services.sync_service import SyncService
from app.services.tiered_pipeline import TieredPipeline
from app.services.track_service import TrackService
from app.services.transition_history import TransitionHistoryService
from app.services.workflows import (
    AnalyzeTrackWorkflow,
    BuildSetWorkflow,
    DeliverSetWorkflow,
    ImportTracksWorkflow,
    SyncPlaylistWorkflow,
)
from app.ym.client import YandexMusicClient


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
    from app.db.repositories.metadata import MetadataRepository

    return MetadataService(MetadataRepository(session))


def get_import_service(
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    metadata: MetadataService = Depends(get_metadata_service),  # noqa: B008
    ingestion_repo: IngestionRepository = Depends(get_ingestion_repo),  # noqa: B008
) -> ImportService:
    return ImportService(track_repo, ym, metadata, ingestion_repo)


def get_candidate_service(
    repo: CandidateRepository = Depends(get_candidate_repo),  # noqa: B008
) -> CandidateService:
    return CandidateService(repo)


def get_embedding_service(
    repo: EmbeddingRepository = Depends(get_embedding_repo),  # noqa: B008
) -> EmbeddingService:
    return EmbeddingService(repo)


def get_import_tracks_workflow(
    import_service: ImportService = Depends(get_import_service),  # noqa: B008
    tiered_pipeline: TieredPipeline = Depends(get_tiered_pipeline),  # noqa: B008
) -> ImportTracksWorkflow:
    return ImportTracksWorkflow(import_service, tiered_pipeline)


def get_analyze_track_workflow(
    audio_service: AudioService = Depends(get_audio_service),  # noqa: B008
    tiered_pipeline: TieredPipeline = Depends(get_tiered_pipeline),  # noqa: B008
    playlist_repo: PlaylistRepository = Depends(get_playlist_repo),  # noqa: B008
) -> AnalyzeTrackWorkflow:
    return AnalyzeTrackWorkflow(audio_service, tiered_pipeline, playlist_repo)


def get_build_set_workflow(
    set_service: SetService = Depends(get_set_service),  # noqa: B008
    tiered_pipeline: TieredPipeline = Depends(get_tiered_pipeline),  # noqa: B008
    playlist_repo: PlaylistRepository = Depends(get_playlist_repo),  # noqa: B008
) -> BuildSetWorkflow:
    return BuildSetWorkflow(set_service, tiered_pipeline, playlist_repo)


def get_sync_playlist_workflow(
    sync_service: SyncService = Depends(get_sync_service),  # noqa: B008
) -> SyncPlaylistWorkflow:
    return SyncPlaylistWorkflow(sync_service)


def get_deliver_set_workflow(
    delivery_service: DeliveryService = Depends(get_delivery_service),  # noqa: B008
    tiered_pipeline: TieredPipeline = Depends(get_tiered_pipeline),  # noqa: B008
    sync_workflow: SyncPlaylistWorkflow = Depends(get_sync_playlist_workflow),  # noqa: B008
) -> DeliverSetWorkflow:
    return DeliverSetWorkflow(delivery_service, tiered_pipeline, sync_workflow)


def get_transition_history_service(
    repo: TransitionHistoryRepository = Depends(get_transition_history_repo),  # noqa: B008
) -> TransitionHistoryService:
    return TransitionHistoryService(repo)
