"""Transition candidate repository — DB operations for candidate pruning."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dj_music.models.audio import TrackAudioFeaturesComputed
from dj_music.models.transition import TransitionCandidate
from dj_music.repositories.base import BaseRepository
from dj_music.schemas.audio import TrackFeatures


class CandidateRepository(BaseRepository[TransitionCandidate]):
    """Repository for :class:`TransitionCandidate` storage and queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TransitionCandidate)

    async def load_features(
        self,
        track_ids: list[int] | None,
    ) -> dict[int, TrackFeatures]:
        """Load TrackFeatures for tracks in a single batch query."""
        stmt = select(TrackAudioFeaturesComputed)
        if track_ids is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.track_id.in_(track_ids))
        result = await self.session.execute(stmt)
        return {row.track_id: TrackFeatures.from_db(row) for row in result.scalars().all()}

    async def delete_candidates_for_tracks(self, track_ids: list[int]) -> None:
        """Remove existing candidates for the given tracks."""
        stmt = delete(TransitionCandidate).where(TransitionCandidate.from_track_id.in_(track_ids))
        await self.session.execute(stmt)

    async def bulk_insert(self, candidates: list[TransitionCandidate]) -> None:
        """Bulk insert candidate records."""
        if candidates:
            self.session.add_all(candidates)
            await self.session.flush()

    async def get_candidates_for_track(
        self,
        track_id: int,
        limit: int = 20,
    ) -> list[TransitionCandidate]:
        """Get pre-filtered candidates for a specific track, ordered by BPM distance."""
        stmt = (
            select(TransitionCandidate)
            .where(TransitionCandidate.from_track_id == track_id)
            .order_by(TransitionCandidate.bpm_distance)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_candidate_pair(
        self,
        from_track_id: int,
        to_track_id: int,
    ) -> TransitionCandidate | None:
        """Get a specific candidate pair, or None if it doesn't exist."""
        stmt = select(TransitionCandidate).where(
            TransitionCandidate.from_track_id == from_track_id,
            TransitionCandidate.to_track_id == to_track_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_candidates(self, track_id: int | None = None) -> int:
        """Count total candidates, optionally for a specific track."""
        stmt = select(func.count()).select_from(TransitionCandidate)
        if track_id is not None:
            stmt = stmt.where(TransitionCandidate.from_track_id == track_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()
