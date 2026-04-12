"""Adaptive Energy Arc — adjusts energy curve based on session feedback.

Instead of rigid template arcs, this service learns the DJ's preferred
energy flow from transition history and feedback patterns.
"""

from __future__ import annotations

from typing import Any

from dj_music.repositories.transition_history import TransitionHistoryRepository


class AdaptiveArcService:
    """Builds energy arc profiles from session data."""

    def __init__(self, history_repo: TransitionHistoryRepository) -> None:
        self._history = history_repo

    async def compute_preferred_arc(
        self,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Compute energy arc from recent transition history.

        Returns list of {position: 0.0-1.0, energy: LUFS, mood: str}
        representing the DJ's actual energy flow.
        """
        entries = await self._history.get_history(limit=limit)
        if not entries:
            return []

        arc: list[dict[str, Any]] = []
        total = len(entries)
        for i, entry in enumerate(reversed(entries)):  # chronological order
            position = i / max(1, total - 1)
            arc.append(
                {
                    "position": round(position, 3),
                    "from_track_id": entry.from_track_id,
                    "to_track_id": entry.to_track_id,
                    "score": entry.overall_score,
                    "style": entry.style,
                    "reaction": entry.user_reaction,
                }
            )
        return arc

    async def get_energy_trend(self, last_n: int = 10) -> str:
        """Analyze recent transitions to determine energy direction.

        Returns: 'rising', 'falling', 'plateau', or 'unknown'
        """
        entries = await self._history.get_history(limit=last_n)
        if len(entries) < 3:
            return "unknown"

        scores = [e.overall_score for e in entries if e.overall_score is not None]
        if len(scores) < 3:
            return "unknown"

        # Compare first half avg vs second half avg
        mid = len(scores) // 2
        first_half = sum(scores[:mid]) / mid
        second_half = sum(scores[mid:]) / (len(scores) - mid)

        delta = second_half - first_half
        if delta > 0.05:
            return "rising"
        if delta < -0.05:
            return "falling"
        return "plateau"

    async def suggest_energy_direction(self, last_n: int = 10) -> dict[str, Any]:
        """Suggest what energy direction the next track should take."""
        trend = await self.get_energy_trend(last_n)
        entries = await self._history.get_history(limit=last_n)

        liked = sum(1 for e in entries if e.user_reaction == "like")
        skipped = sum(1 for e in entries if e.user_reaction == "skip")

        if skipped > liked and trend == "plateau":
            return {
                "suggestion": "ramp_up",
                "reason": "session feels stale, more skips than likes",
            }
        if trend == "rising":
            return {"suggestion": "maintain", "reason": "energy rising, keep momentum"}
        if trend == "falling":
            return {"suggestion": "ramp_up", "reason": "energy dropping, needs a boost"}
        return {"suggestion": "any", "reason": "no clear trend"}
