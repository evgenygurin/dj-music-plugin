"""Repository dependency factories."""

from __future__ import annotations

from fastmcp.dependencies import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dj_music.di.db import get_db_session
from dj_music.repositories.audio import AudioRepository
from dj_music.repositories.candidate import CandidateRepository
from dj_music.repositories.embedding import EmbeddingRepository
from dj_music.repositories.export import ExportRepository
from dj_music.repositories.feature import FeatureRepository
from dj_music.repositories.ingestion import IngestionRepository
from dj_music.repositories.playlist import PlaylistRepository
from dj_music.repositories.set import SetRepository
from dj_music.repositories.track import TrackRepository
from dj_music.repositories.transition import TransitionRepository
from dj_music.repositories.transition_history import TransitionHistoryRepository


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
