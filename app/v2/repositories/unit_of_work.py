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

from app.v2.repositories.audio_file import AudioFileRepository
from app.v2.repositories.key import KeyEdgeRepository, KeyRepository
from app.v2.repositories.playlist import PlaylistRepository
from app.v2.repositories.provider_metadata import (
    ProviderMetadataRepository,
    RawProviderResponseRepository,
    YandexMetadataRepository,
)
from app.v2.repositories.scoring_profile import ScoringProfileRepository
from app.v2.repositories.set import SetRepository, SetVersionRepository
from app.v2.repositories.track import TrackRepository
from app.v2.repositories.track_affinity import TrackAffinityRepository
from app.v2.repositories.track_features import TrackFeaturesRepository
from app.v2.repositories.track_feedback import TrackFeedbackRepository
from app.v2.repositories.transition import TransitionRepository
from app.v2.repositories.transition_history import TransitionHistoryRepository


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
