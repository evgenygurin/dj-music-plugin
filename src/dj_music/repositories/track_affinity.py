"""Track affinity repository."""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dj_music.models.track_affinity import TrackAffinity
from dj_music.models.transition_history import TransitionHistory
from dj_music.repositories.base import BaseRepository


class TrackAffinityRepository(BaseRepository[TrackAffinity]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TrackAffinity)

    async def get_pair(self, track_a: int, track_b: int) -> TrackAffinity | None:
        stmt = select(TrackAffinity).where(
            TrackAffinity.track_a_id == track_a,
            TrackAffinity.track_b_id == track_b,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_recommendations(self, track_id: int, limit: int = 10) -> list[dict[str, Any]]:
        """Top-N tracks with best affinity for a given track."""
        stmt = (
            select(
                TrackAffinity.track_b_id.label("track_id"),
                TrackAffinity.net_sentiment,
                TrackAffinity.play_count,
                TrackAffinity.avg_score,
            )
            .where(TrackAffinity.track_a_id == track_id)
            .where(TrackAffinity.ban_count == 0)
            .where(TrackAffinity.net_sentiment > 0)
            .order_by(desc(TrackAffinity.net_sentiment))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [dict(row._mapping) for row in result.all()]

    async def refresh_from_history(self) -> int:
        """Rebuild all affinity rows from transition_history. Returns count."""
        # Aggregate transition_history into affinity
        agg = select(
            TransitionHistory.from_track_id.label("track_a_id"),
            TransitionHistory.to_track_id.label("track_b_id"),
            func.count().label("play_count"),
            func.avg(TransitionHistory.overall_score).label("avg_score"),
            func.sum(
                func.cast(
                    TransitionHistory.user_reaction == "like",
                    type_=func.integer if False else None,
                )
            ).label("like_count_raw"),
            func.max(TransitionHistory.created_at).label("last_played_at"),
        ).group_by(TransitionHistory.from_track_id, TransitionHistory.to_track_id)
        result = await self.session.execute(agg)
        rows = result.all()

        count = 0
        for row in rows:
            mapping = row._mapping
            track_a = mapping["track_a_id"]
            track_b = mapping["track_b_id"]
            play_count = mapping["play_count"]

            # Count reactions separately
            reactions_stmt = (
                select(
                    TransitionHistory.user_reaction,
                    func.count().label("cnt"),
                )
                .where(TransitionHistory.from_track_id == track_a)
                .where(TransitionHistory.to_track_id == track_b)
                .where(TransitionHistory.user_reaction.isnot(None))
                .group_by(TransitionHistory.user_reaction)
            )
            reactions_result = await self.session.execute(reactions_stmt)
            reaction_counts: dict[str, int] = {}
            for rr in reactions_result.all():
                reaction_counts[rr._mapping["user_reaction"]] = rr._mapping["cnt"]

            like_count = reaction_counts.get("like", 0)
            ban_count = reaction_counts.get("ban", 0)
            skip_count = reaction_counts.get("skip", 0)
            net = (like_count - ban_count - 0.5 * skip_count) / max(1, play_count)

            existing = await self.get_pair(track_a, track_b)
            if existing:
                existing.play_count = play_count
                existing.avg_score = mapping["avg_score"]
                existing.like_count = like_count
                existing.ban_count = ban_count
                existing.skip_count = skip_count
                existing.net_sentiment = net
                existing.last_played_at = mapping["last_played_at"]
            else:
                self.session.add(
                    TrackAffinity(
                        track_a_id=track_a,
                        track_b_id=track_b,
                        play_count=play_count,
                        avg_score=mapping["avg_score"],
                        like_count=like_count,
                        ban_count=ban_count,
                        skip_count=skip_count,
                        net_sentiment=net,
                        last_played_at=mapping["last_played_at"],
                    )
                )
            count += 1

        await self.session.flush()
        return count
