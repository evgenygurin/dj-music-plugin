"""FastMCP dependency injection factories.

All dependencies use Depends() — hidden from tool schemas.
DB session is cached per-request: multiple repos share one transaction.
"""

from fastmcp.server.dependencies import get_context

from app.controllers.dependencies.audio import (
    get_audio_service,
    get_tiered_pipeline,
    get_timeseries_storage,
)
from app.controllers.dependencies.db import get_db_session
from app.controllers.dependencies.external import (
    get_analyzer_registry,
    get_transition_cache,
    get_ym_client,
)
from app.controllers.dependencies.repos import (
    get_audio_repo,
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
from app.controllers.dependencies.services import (
    get_analyze_track_workflow,
    get_build_set_workflow,
    get_candidate_service,
    get_curation_service,
    get_deliver_set_workflow,
    get_delivery_service,
    get_discovery_service,
    get_embedding_service,
    get_import_service,
    get_import_tracks_workflow,
    get_metadata_service,
    get_playlist_service,
    get_prefetch_service,
    get_reasoning_service,
    get_search_service,
    get_set_service,
    get_sync_playlist_workflow,
    get_sync_service,
    get_track_service,
    get_transition_history_service,
)
from app.controllers.dependencies.uow import get_uow

__all__ = [
    "get_analyze_track_workflow",
    "get_analyzer_registry",
    "get_audio_repo",
    "get_audio_service",
    "get_build_set_workflow",
    "get_candidate_repo",
    "get_candidate_service",
    "get_context",
    "get_curation_service",
    "get_db_session",
    "get_deliver_set_workflow",
    "get_delivery_service",
    "get_discovery_service",
    "get_embedding_repo",
    "get_embedding_service",
    "get_export_repo",
    "get_feature_repo",
    "get_import_service",
    "get_import_tracks_workflow",
    "get_ingestion_repo",
    "get_metadata_service",
    "get_playlist_repo",
    "get_playlist_service",
    "get_prefetch_service",
    "get_reasoning_service",
    "get_search_service",
    "get_set_repo",
    "get_set_service",
    "get_sync_playlist_workflow",
    "get_sync_service",
    "get_tiered_pipeline",
    "get_timeseries_storage",
    "get_track_repo",
    "get_track_service",
    "get_transition_cache",
    "get_transition_history_repo",
    "get_transition_history_service",
    "get_transition_repo",
    "get_uow",
    "get_ym_client",
]
