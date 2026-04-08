"""Transition scoring engine — orchestrator for the 6-component formula.

Pure domain logic: no I/O, no DB, no async. The actual scoring lives in
``app/domain/transition/components/`` (one pure function per component);
this file only checks hard constraints, dispatches to the components,
and combines the results with weights.

See docs/transition-scoring.md for the full algorithm description and
docs/superpowers/specs/2026-04-08-transition-system-redesign.md for the
redesign that produced this layout.
"""

from __future__ import annotations

from app.core.constants import DEFAULT_TRANSITION_WEIGHTS
from app.core.track_features import TrackFeatures
from app.transition.components import (
    score_bpm,
    score_energy,
    score_groove,
    score_harmonic,
    score_spectral,
    score_timbral,
)
from app.transition.hard_constraints import check_hard_constraints
from app.transition.intent import INTENT_WEIGHT_MODIFIERS, TransitionIntent
from app.transition.score import TransitionScore
from app.transition.section_context import SectionContext
from app.transition.style import recommend_style, style_profile
from app.transition.weights import DRUM_ONLY_WEIGHT_OVERRIDE

__all__ = [
    "TransitionScore",
    "TransitionScorer",
    "recommend_style",
    "style_profile",
]


class TransitionScorer:
    """Compute transition quality between two tracks.

    Uses ``settings.*`` (via ``check_hard_constraints``) for hard reject
    thresholds and the supplied ``weights`` dict (or
    ``DEFAULT_TRANSITION_WEIGHTS``) for the weighted sum.
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
    ) -> None:
        self.weights = weights or dict(DEFAULT_TRANSITION_WEIGHTS)

    def score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
    ) -> TransitionScore:
        """Compute the full 6-component score.

        Args:
            from_t: Features of the outgoing track.
            to_t: Features of the incoming track.
            intent: Optional context-aware intent for weight modifiers.
                When provided, per-intent weights override instance defaults.
            section_context: Optional structural context for the mix
                windows. When both sides are percussion-only sections,
                ``DRUM_ONLY_WEIGHT_OVERRIDE`` is used for the weighted
                sum and ``score_harmonic`` applies its drum-only floor.
                Drum-only override takes precedence over ``intent``.
        """
        rejection = check_hard_constraints(from_t, to_t)
        if rejection is not None:
            return rejection

        # Pick weight set: drum-only > intent override > instance default
        if section_context is not None and section_context.is_drum_only_pair:
            weights: dict[str, float] | None = DRUM_ONLY_WEIGHT_OVERRIDE
        elif intent is not None:
            weights = INTENT_WEIGHT_MODIFIERS[intent]
        else:
            weights = None

        return self._compute_score(from_t, to_t, weights=weights, section_context=section_context)

    def score_with_candidates(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        candidate_bpm_distance: float | None = None,
        candidate_key_distance: int | None = None,
        candidate_energy_delta: float | None = None,
    ) -> TransitionScore:
        """Score a transition, reusing pre-computed candidate distances.

        When transition candidates are available, the BPM/key/energy
        distances have already been computed by ``CandidateService``.
        Skip recomputing them for hard-constraint checks.

        Falls back to a full ``score()`` if no candidate data is provided.
        """
        rejection = check_hard_constraints(
            from_t,
            to_t,
            pre_bpm_dist=candidate_bpm_distance,
            pre_key_dist=candidate_key_distance,
            pre_energy_delta=candidate_energy_delta,
        )
        if rejection is not None:
            return rejection

        return self._compute_score(from_t, to_t)

    # ── Shared internals ───────────────────────────

    def _compute_score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        weights: dict[str, float] | None = None,
        section_context: SectionContext | None = None,
    ) -> TransitionScore:
        """Run all 6 component functions and combine them with weights."""
        w = weights or self.weights
        bpm = score_bpm(from_t, to_t)
        harmonic = score_harmonic(from_t, to_t, section_context=section_context)
        energy = score_energy(from_t, to_t)
        spectral = score_spectral(from_t, to_t)
        groove = score_groove(from_t, to_t)
        timbral = score_timbral(from_t, to_t)

        overall = (
            w.get("bpm", 0) * bpm
            + w.get("harmonic", 0) * harmonic
            + w.get("energy", 0) * energy
            + w.get("spectral", 0) * spectral
            + w.get("groove", 0) * groove
            + w.get("timbral", 0) * timbral
        )

        return TransitionScore(
            bpm=bpm,
            harmonic=harmonic,
            energy=energy,
            spectral=spectral,
            groove=groove,
            timbral=timbral,
            overall=overall,
        )


# recommend_style and style_profile live in app/domain/transition/style.py
# and are re-exported above so existing
# `from app.transition.scorer import recommend_style` calls
# remain valid.
