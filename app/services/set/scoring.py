"""Set scoring sub-service — score transitions between tracks and within sets."""

from __future__ import annotations

from typing import Any

from app.core.errors import NotFoundError
from app.domain.transition import TransitionScore, recommend_style, style_profile
from app.models.transition import Transition
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

    @staticmethod
    def _format_pair_response(
        from_id: int,
        to_id: int,
        *,
        overall: float | None,
        bpm: float | None,
        harmonic: float | None,
        energy: float | None,
        spectral: float | None,
        groove: float | None,
        timbral: float | None,
        hard_reject: bool | None,
        reject_reason: str | None,
        cached: bool,
    ) -> dict[str, Any]:
        """Build the canonical pair-score response envelope.

        All 6 components are surfaced, plus ``hard_reject`` /
        ``reject_reason`` so cache hits and fresh scores are
        indistinguishable to callers.
        """

        def _round(v: float | None) -> float | None:
            return round(v, 4) if v is not None else None

        # Reconstruct a TransitionScore from the persisted/computed
        # numbers so the style decision uses the SAME logic for cache
        # hits and fresh scores. Missing components default to 0 — they
        # only land in the response when the recommendation is genuine
        # (we hide style entirely when overall is None).
        recommended_style: str | None = None
        recommended_bars: float | int | None = None
        if overall is not None:
            synthetic = TransitionScore(
                bpm=bpm or 0.0,
                harmonic=harmonic or 0.0,
                energy=energy or 0.0,
                spectral=spectral or 0.0,
                groove=groove or 0.0,
                timbral=timbral or 0.0,
                overall=overall,
                hard_reject=bool(hard_reject) if hard_reject is not None else False,
                reject_reason=reject_reason,
            )
            style = recommend_style(synthetic)
            recommended_style = style.value
            profile_bars = style_profile(style)["bars"]
            recommended_bars = profile_bars if isinstance(profile_bars, int | float) else None

        return {
            "from_track_id": from_id,
            "to_track_id": to_id,
            "overall_quality": _round(overall),
            "bpm_score": _round(bpm),
            "harmonic_score": _round(harmonic),
            "energy_score": _round(energy),
            "spectral_score": _round(spectral),
            "groove_score": _round(groove),
            "timbral_score": _round(timbral),
            "hard_reject": bool(hard_reject) if hard_reject is not None else False,
            "reject_reason": reject_reason,
            "cached": cached,
            "recommended_style": recommended_style,
            "recommended_bars": recommended_bars,
        }

    async def score_pair(self, from_id: int, to_id: int) -> dict[str, Any]:
        """Score transition between two tracks. Save to DB."""
        existing = await self._transitions.get_score(from_id, to_id)
        if existing and existing.overall_quality is not None:
            return self._format_pair_response(
                from_id,
                to_id,
                overall=existing.overall_quality,
                bpm=existing.bpm_score,
                harmonic=existing.harmonic_score,
                energy=existing.energy_score,
                spectral=existing.spectral_score,
                groove=existing.groove_score,
                timbral=existing.timbral_score,
                hard_reject=existing.hard_reject,
                reject_reason=existing.reject_reason,
                cached=True,
            )

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

        final_quality = 0.0 if score.hard_reject else score.overall

        transition = Transition(
            from_track_id=from_id,
            to_track_id=to_id,
            overall_quality=final_quality,
            bpm_score=score.bpm,
            harmonic_score=score.harmonic,
            energy_score=score.energy,
            spectral_score=score.spectral,
            groove_score=score.groove,
            timbral_score=score.timbral,
            hard_reject=score.hard_reject,
            reject_reason=score.reject_reason,
        )
        await self._transitions.save_score(transition)

        return self._format_pair_response(
            from_id,
            to_id,
            overall=final_quality,
            bpm=score.bpm,
            harmonic=score.harmonic,
            energy=score.energy,
            spectral=score.spectral,
            groove=score.groove,
            timbral=score.timbral,
            hard_reject=score.hard_reject,
            reject_reason=score.reject_reason,
            cached=False,
        )

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
        hard_conflicts = [t for t in scored if t.get("hard_reject") is True]

        # Average only over non-reject, scored transitions.
        soft_scored = [t for t in scored if not t.get("hard_reject")]
        avg_score: float | None = None
        if soft_scored:
            avg_score = sum(float(t["overall_quality"]) for t in soft_scored) / len(soft_scored)

        return {
            "set_id": set_id,
            "version_id": latest.id,
            "total_transitions": len(transitions_data),
            "scored_transitions": len(scored),
            "hard_conflicts": len(hard_conflicts),
            "avg_score": avg_score,
            "transitions": transitions_data,
        }

    async def get_transition_candidates(self, track_id: int, top_n: int = 10) -> dict[str, Any]:
        """Get best transition candidates for a track. Stub — returns empty list."""
        return {
            "track_id": track_id,
            "candidates": [],
            "note": "Transition candidate search not yet implemented",
        }
