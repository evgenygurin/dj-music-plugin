"""Unit of Work — transaction boundary = tool call.

Phase 2: adds lazy ``@cached_property`` accessors for every registered entity.
Each property caches the repository instance so calls like
``uow.tracks`` return the same object within one UoW lifetime.
"""

from __future__ import annotations

from functools import cached_property
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audio_file import AudioFileRepository
from app.repositories.cross_similarity import CrossSimilarityRepository
from app.repositories.feature_extraction import FeatureExtractionRunRepository
from app.repositories.key import KeyEdgeRepository, KeyRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.provider_metadata import (
    ProviderMetadataRepository,
    RawProviderResponseRepository,
    YandexMetadataRepository,
)
from app.repositories.scoring_profile import ScoringProfileRepository
from app.repositories.set import SetRepository, SetVersionRepository
from app.repositories.stem_features import StemFeaturesRepository
from app.repositories.track import TrackRepository
from app.repositories.track_affinity import TrackAffinityRepository
from app.repositories.track_embedding import TrackEmbeddingRepository
from app.repositories.track_features import TrackFeaturesRepository
from app.repositories.track_feedback import TrackFeedbackRepository
from app.repositories.track_section import TrackSectionRepository
from app.repositories.transition import TransitionRepository
from app.repositories.transition_history import TransitionHistoryRepository


class UnitOfWork:
    """Commit on success, rollback on exception."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc is None:
            await self.session.commit()
        else:
            await self.session.rollback()

    # ── lazy repository properties ────────────────────

    @cached_property
    def tracks(self) -> TrackRepository:
        return TrackRepository(self.session)

    @cached_property
    def playlists(self) -> PlaylistRepository:
        return PlaylistRepository(self.session)

    @cached_property
    def sets(self) -> SetRepository:
        return SetRepository(self.session)

    @cached_property
    def set_versions(self) -> SetVersionRepository:
        return SetVersionRepository(self.session)

    @cached_property
    def audio_files(self) -> AudioFileRepository:
        return AudioFileRepository(self.session)

    @cached_property
    def track_features(self) -> TrackFeaturesRepository:
        return TrackFeaturesRepository(self.session)

    @cached_property
    def transitions(self) -> TransitionRepository:
        return TransitionRepository(self.session)

    @cached_property
    def transition_history(self) -> TransitionHistoryRepository:
        return TransitionHistoryRepository(self.session)

    @cached_property
    def track_feedback(self) -> TrackFeedbackRepository:
        return TrackFeedbackRepository(self.session)

    @cached_property
    def track_affinity(self) -> TrackAffinityRepository:
        return TrackAffinityRepository(self.session)

    @cached_property
    def scoring_profiles(self) -> ScoringProfileRepository:
        return ScoringProfileRepository(self.session)

    @cached_property
    def provider_metadata(self) -> ProviderMetadataRepository:
        return ProviderMetadataRepository(self.session)

    @cached_property
    def yandex_metadata(self) -> YandexMetadataRepository:
        return YandexMetadataRepository(self.session)

    @cached_property
    def raw_provider_responses(self) -> RawProviderResponseRepository:
        return RawProviderResponseRepository(self.session)

    @cached_property
    def keys(self) -> KeyRepository:
        return KeyRepository(self.session)

    @cached_property
    def key_edges(self) -> KeyEdgeRepository:
        return KeyEdgeRepository(self.session)

    @cached_property
    def stem_features(self) -> StemFeaturesRepository:
        return StemFeaturesRepository(self.session)

    @cached_property
    def track_embeddings(self) -> TrackEmbeddingRepository:
        return TrackEmbeddingRepository(self.session)

    @cached_property
    def cross_similarity(self) -> CrossSimilarityRepository:
        return CrossSimilarityRepository(self.session)

    @cached_property
    def track_sections(self) -> TrackSectionRepository:
        return TrackSectionRepository(self.session)

    @cached_property
    def feature_extraction_runs(self) -> FeatureExtractionRunRepository:
        return FeatureExtractionRunRepository(self.session)
