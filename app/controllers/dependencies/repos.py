"""Repository dependency factories."""

from __future__ import annotations

from fastmcp.dependencies import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies.db import get_db_session
from app.db.repositories.audio import AudioRepository
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


def get_track_repo(session: AsyncSession = Depends(get_db_session)) -> TrackRepository:  # noqa: B008
    return TrackRepository(session)


def get_playlist_repo(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> PlaylistRepository:
    return PlaylistRepository(session)


def get_set_repo(session: AsyncSession = Depends(get_db_session)) -> SetRepository:  # noqa: B008
    return SetRepository(session)


def get_feature_repo(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> FeatureRepository:
    return FeatureRepository(session)


def get_transition_repo(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> TransitionRepository:
    return TransitionRepository(session)


def get_export_repo(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ExportRepository:
    return ExportRepository(session)


def get_ingestion_repo(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> IngestionRepository:
    return IngestionRepository(session)


def get_audio_repo(session: AsyncSession = Depends(get_db_session)) -> AudioRepository:  # noqa: B008
    return AudioRepository(session)


def get_embedding_repo(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> EmbeddingRepository:
    return EmbeddingRepository(session)


def get_candidate_repo(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> CandidateRepository:
    return CandidateRepository(session)


def get_transition_history_repo(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> TransitionHistoryRepository:
    return TransitionHistoryRepository(session)
