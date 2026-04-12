"""Transition history service — business logic for transition memory."""

from __future__ import annotations

from typing import Any

from app.db.models.transition_history import TransitionHistory
from app.db.repositories.transition_history import TransitionHistoryRepository


class TransitionHistoryService:
    HISTORY_LIKE_BOOST = 0.10
    HISTORY_BAN_REJECT = True
    HISTORY_SKIP_PENALTY = 0.15
    HISTORY_LISTENED_BOOST = 0.03

    def __init__(self, repo: TransitionHistoryRepository) -> None:
        self._repo = repo

    async def log_transition(
        self,
        from_track_id: int,
        to_track_id: int,
        overall_score: float | None = None,
        bpm_score: float | None = None,
        harmonic_score: float | None = None,
        energy_score: float | None = None,
        spectral_score: float | None = None,
        groove_score: float | None = None,
        timbral_score: float | None = None,
        style: str | None = None,
        duration_sec: float | None = None,
        tempo_match_ratio: float | None = None,
        user_reaction: str | None = None,
        session_id: str | None = None,
    ) -> TransitionHistory:
        entry = TransitionHistory(
            from_track_id=from_track_id,
            to_track_id=to_track_id,
            overall_score=overall_score,
            bpm_score=bpm_score,
            harmonic_score=harmonic_score,
            energy_score=energy_score,
            spectral_score=spectral_score,
            groove_score=groove_score,
            timbral_score=timbral_score,
            style=style,
            duration_sec=duration_sec,
            tempo_match_ratio=tempo_match_ratio,
            user_reaction=user_reaction,
            session_id=session_id,
        )
        return await self._repo.log(entry)

    async def get_history(
        self,
        from_track_id: int | None = None,
        to_track_id: int | None = None,
        limit: int = 20,
        min_score: float | None = None,
    ) -> list[TransitionHistory]:
        return await self._repo.get_history(from_track_id, to_track_id, limit, min_score)

    async def get_best_pairs(self, track_id: int, limit: int = 10) -> list[dict[str, Any]]:
        return await self._repo.get_best_pairs(track_id, limit)

    async def update_reaction(self, entry_id: int, reaction: str) -> None:
        valid = {"like", "ban", "skip", "listened"}
        if reaction not in valid:
            from dj_music.core.errors import ValidationError

            raise ValidationError(
                f"Invalid reaction '{reaction}'. Must be one of: {', '.join(sorted(valid))}"
            )
        await self._repo.update_reaction(entry_id, reaction)

    async def apply_history_bonus(self, from_id: int, to_id: int, base_score: float) -> float:
        reaction = await self._repo.get_pair_reaction(from_id, to_id)
        if reaction is None:
            return base_score
        if reaction == "like":
            return min(1.0, base_score + self.HISTORY_LIKE_BOOST)
        if reaction == "ban":
            return 0.0
        if reaction == "skip":
            return max(0.0, base_score - self.HISTORY_SKIP_PENALTY)
        if reaction == "listened":
            return min(1.0, base_score + self.HISTORY_LISTENED_BOOST)
        return base_score
