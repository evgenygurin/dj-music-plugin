"""Track features repository — batch load for scoring + targeted mood writes."""

from __future__ import annotations

from sqlalchemy import select, update

from app.models.track_features import TrackAudioFeaturesComputed
from app.repositories.base import BaseRepository
from app.shared.errors import NotFoundError


class TrackFeaturesRepository(BaseRepository[TrackAudioFeaturesComputed]):
    model = TrackAudioFeaturesComputed

    async def get_scoring_features_batch(
        self, track_ids: list[int]
    ) -> dict[int, TrackAudioFeaturesComputed]:
        """One SQL for N tracks; missing rows are silently omitted."""
        if not track_ids:
            return {}
        stmt = select(TrackAudioFeaturesComputed).where(
            TrackAudioFeaturesComputed.track_id.in_(track_ids)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return {r.track_id: r for r in rows}

    async def set_mood(self, track_id: int, *, mood: str, confidence: float) -> None:
        """Update mood + confidence on an existing features row."""
        stmt = (
            update(TrackAudioFeaturesComputed)
            .where(TrackAudioFeaturesComputed.track_id == track_id)
            .values(mood=mood, mood_confidence=confidence)
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise NotFoundError("track_features", track_id)
        await self.session.flush()

    async def get_analysis_level(self, track_id: int) -> int:
        """Return current analysis_level (0 if no row)."""
        stmt = select(TrackAudioFeaturesComputed.analysis_level).where(
            TrackAudioFeaturesComputed.track_id == track_id
        )
        row = await self.session.scalar(stmt)
        return int(row) if row is not None else 0
