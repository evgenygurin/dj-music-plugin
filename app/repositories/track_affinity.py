"""TrackAffinity repository."""

from __future__ import annotations

from sqlalchemy import desc, select

from app.models.track_affinity import TrackAffinity
from app.repositories.base import BaseRepository


class TrackAffinityRepository(BaseRepository[TrackAffinity]):
    model = TrackAffinity

    async def get_pair(self, track_a_id: int, track_b_id: int) -> TrackAffinity | None:
        stmt = select(TrackAffinity).where(
            TrackAffinity.track_a_id == track_a_id,
            TrackAffinity.track_b_id == track_b_id,
        )
        return await self.session.scalar(stmt)  # type: ignore[no-any-return]

    async def recommend(self, track_id: int, limit: int = 10) -> list[TrackAffinity]:
        """Return the top-``limit`` neighbours of ``track_id`` ranked by
        ``net_sentiment`` (the denormalised score column populated by
        the feedback handler), falling back to play count for pairs
        without an explicit sentiment signal yet.
        """
        stmt = (
            select(TrackAffinity)
            .where((TrackAffinity.track_a_id == track_id) | (TrackAffinity.track_b_id == track_id))
            .order_by(desc(TrackAffinity.net_sentiment), desc(TrackAffinity.play_count))
            .limit(limit)
        )
        return list((await self._execute(stmt)).scalars())
