"""Track affinity service."""

from __future__ import annotations

from typing import Any

from app.db.repositories.track_affinity import TrackAffinityRepository


class TrackAffinityService:
    def __init__(self, repo: TrackAffinityRepository) -> None:
        self._repo = repo

    async def refresh(self) -> int:
        """Rebuild affinity matrix from transition_history."""
        return await self._repo.refresh_from_history()

    async def get_pair(self, track_a: int, track_b: int) -> dict[str, Any] | None:
        row = await self._repo.get_pair(track_a, track_b)
        if row is None:
            return None
        return {
            "track_a_id": row.track_a_id,
            "track_b_id": row.track_b_id,
            "play_count": row.play_count,
            "avg_score": row.avg_score,
            "net_sentiment": row.net_sentiment,
            "like_count": row.like_count,
            "ban_count": row.ban_count,
        }

    async def get_recommendations(self, track_id: int, limit: int = 10) -> list[dict[str, Any]]:
        return await self._repo.get_recommendations(track_id, limit)
