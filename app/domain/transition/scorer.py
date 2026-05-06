"""Transition scoring engine — orchestrator for the stem-aware formula.

Pure domain logic: no I/O, no DB, no async. Combines BPM + energy
component scores with the four Neural Mix stem compats from
``neural_mix.py`` into a single ``TransitionScore``.

See docs/transition-scoring.md for the full algorithm description.
"""

from __future__ import annotations

from app.domain.transition.components import score_bpm, score_energy
from app.domain.transition.hard_constraints import check_hard_constraints
from app.domain.transition.intent import INTENT_WEIGHT_MODIFIERS, TransitionIntent
from app.domain.transition.neural_mix import (
    NeuralMixScorer,
    NeuralMixStem,
    NeuralMixTransition,
)
from app.domain.transition.score import TransitionScore
from app.domain.transition.section_context import SectionContext
from app.domain.transition.weights import DEFAULT_WEIGHTS
from app.shared.features import TrackFeatures

__all__ = [
    "TransitionScore",
    "TransitionScorer",
]


class TransitionScorer:
    """Compute transition quality between two tracks.

    Uses ``settings.*`` (via ``check_hard_constraints``) for hard reject
    thresholds and the supplied ``weights`` dict (or ``DEFAULT_WEIGHTS``
    from ``weights.py``) for the weighted sum. Stem compatibility scores
    come from ``NeuralMixScorer``; the orchestrator collapses them into
    the public six-field ``TransitionScore`` shape and exposes the
    Neural Mix scorer's ``best_transition`` argmax.
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
    ) -> None:
        self.weights = weights or dict(DEFAULT_WEIGHTS)
        self._neural = NeuralMixScorer()

    def score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
    ) -> TransitionScore:
        """Compute the full six-component score.

        ``section_context`` is currently accepted but unused — the picker
        (``app.domain.transition.picker``) consumes it to pick the right
        Neural Mix preset; the scorer itself stays context-free in v1.3.
        """
        del section_context  # reserved for future per-section weight overrides

        rejection = check_hard_constraints(from_t, to_t)
        if rejection is not None:
            return rejection

        weights = INTENT_WEIGHT_MODIFIERS[intent] if intent is not None else self.weights
        return self._compute_score(from_t, to_t, weights=weights)

    def score_with_candidates(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        candidate_bpm_distance: float | None = None,
        candidate_key_distance: int | None = None,
        candidate_energy_delta: float | None = None,
    ) -> TransitionScore:
        """Score reusing pre-computed candidate distances for hard checks."""
        rejection = check_hard_constraints(
            from_t,
            to_t,
            pre_bpm_dist=candidate_bpm_distance,
            pre_key_dist=candidate_key_distance,
            pre_energy_delta=candidate_energy_delta,
        )
        if rejection is not None:
            return rejection

        return self._compute_score(from_t, to_t, weights=self.weights)

    # ── Shared internals ───────────────────────────

    def _compute_score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        weights: dict[str, float],
    ) -> TransitionScore:
        """Compose BPM + energy + four stem compats into a TransitionScore."""
        nm = self._neural.score(from_t, to_t)

        bpm = score_bpm(from_t, to_t)
        energy = score_energy(from_t, to_t)

        # NeuralMixStem → public TransitionScore field name mapping.
        # See ``score.py`` docstring for the conceptual rationale.
        harmonic = nm.stem_scores.get(NeuralMixStem.HARMONICS, 0.0)
        spectral = nm.stem_scores.get(NeuralMixStem.BASS, 0.0)
        groove = nm.stem_scores.get(NeuralMixStem.DRUMS, 0.0)
        timbral = nm.stem_scores.get(NeuralMixStem.VOCALS, 0.0)

        overall = (
            weights.get("bpm", 0.0) * bpm
            + weights.get("harmonic", 0.0) * harmonic
            + weights.get("energy", 0.0) * energy
            + weights.get("spectral", 0.0) * spectral
            + weights.get("groove", 0.0) * groove
            + weights.get("timbral", 0.0) * timbral
        )

        best: NeuralMixTransition | None = nm.best_transition

        return TransitionScore(
            bpm=bpm,
            harmonic=harmonic,
            energy=energy,
            spectral=spectral,
            groove=groove,
            timbral=timbral,
            overall=overall,
            best_transition=best,
        )
