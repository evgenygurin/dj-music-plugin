"""Set scoring sub-service — score transitions between tracks and within sets."""

from __future__ import annotations

from typing import Any

from app.core.errors import NotFoundError
from app.repositories.feature import FeatureRepository
from app.repositories.set import SetRepository
from app.repositories.transition import TransitionRepository
from app.services.transition import TransitionScorer


class SetScoringService:
    """Score transitions for track pairs and full DJ sets."""

    def __init__(
        self,
        set_repo: SetRepository,
        feature_repo: FeatureRepository,
        transition_repo: TransitionRepository,
    ) -> None:
        self._sets = set_repo
        self._features = feature_repo
        self._transitions = transition_repo

    async def score_pair(self, from_id: int, to_id: int) -> dict[str, Any]:
        """Score transition between two tracks. Save to DB."""
        existing = await self._transitions.get_score(from_id, to_id)
        if existing and existing.overall_quality is not None:
            return {
                "from_track_id": from_id,
                "to_track_id": to_id,
                "overall_quality": existing.overall_quality,
                "bpm_score": existing.bpm_score,
                "harmonic_score": existing.harmonic_score,
                "energy_score": existing.energy_score,
                "spectral_score": existing.spectral_score,
                "groove_score": existing.groove_score,
                "cached": True,
            }

        ft_from = await self._features.get_scoring_features(from_id)
        ft_to = await self._features.get_scoring_features(to_id)

        if not ft_from or not ft_to:
            return {
                "from_track_id": from_id,
                "to_track_id": to_id,
                "overall_quality": None,
                "message": "Missing audio features for one or both tracks",
            }

        scorer = TransitionScorer()
        score = scorer.score(ft_from, ft_to)

        from app.models.transition import Transition

        transition = Transition(
            from_track_id=from_id,
            to_track_id=to_id,
            overall_quality=score.overall if not score.hard_reject else 0.0,
            bpm_score=score.bpm,
            harmonic_score=score.harmonic,
            energy_score=score.energy,
            spectral_score=score.spectral,
            groove_score=score.groove,
        )
        await self._transitions.save_score(transition)

        return {
            "from_track_id": from_id,
            "to_track_id": to_id,
            "overall_quality": round(score.overall, 4) if not score.hard_reject else 0.0,
            "bpm_score": round(score.bpm, 4),
            "harmonic_score": round(score.harmonic, 4),
            "energy_score": round(score.energy, 4),
            "spectral_score": round(score.spectral, 4),
            "groove_score": round(score.groove, 4),
            "hard_reject": score.hard_reject,
            "reject_reason": score.reject_reason,
            "cached": False,
        }

    async def score_set_transitions(self, set_id: int) -> dict[str, Any]:
        """Score all sequential transitions in a set."""
        result = await self._sets.load_version_with_items(set_id)
        if result is None:
            raise NotFoundError("SetVersion", f"set_id={set_id}")
        latest, items = result

        transitions_data = []
        for i in range(len(items) - 1):
            score_data = await self.score_pair(items[i].track_id, items[i + 1].track_id)
            score_data["position"] = i
            transitions_data.append(score_data)

        scored = [t for t in transitions_data if t.get("overall_quality") is not None]
        hard_conflicts = [t for t in scored if t.get("overall_quality") == 0.0]

        return {
            "set_id": set_id,
            "version_id": latest.id,
            "total_transitions": len(transitions_data),
            "scored_transitions": len(scored),
            "hard_conflicts": len(hard_conflicts),
            "avg_score": (
                sum(t["overall_quality"] for t in scored if t["overall_quality"])
                / max(1, len(scored) - len(hard_conflicts))
                if scored
                else None
            ),
            "transitions": transitions_data,
        }

    async def get_transition_candidates(self, track_id: int, top_n: int = 10) -> dict[str, Any]:
        """Get best transition candidates for a track. Stub — returns empty list."""
        return {
            "track_id": track_id,
            "candidates": [],
            "note": "Transition candidate search not yet implemented",
        }
