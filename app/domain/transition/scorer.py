"""Transition scoring engine — orchestrator for the stem-aware formula.

Pure domain logic: no I/O, no DB, no async. Combines BPM + energy
component scores with the four Neural Mix stem compats from
``neural_mix.py`` into a single ``TransitionScore``.

See docs/transition-scoring.md for the full algorithm description.
"""

from __future__ import annotations

from collections.abc import Iterable

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

# Default intents the bulk-scoring path materialises. Mirrors the set
# ``infer_intent`` can return: CONTRAST is reserved for future use but
# included so the GA's eager pre-compute never has a cache miss.
_ALL_INTENTS: tuple[TransitionIntent, ...] = (
    TransitionIntent.MAINTAIN,
    TransitionIntent.RAMP_UP,
    TransitionIntent.COOL_DOWN,
    TransitionIntent.CONTRAST,
)

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

    def score_all_intents(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        intents: Iterable[TransitionIntent] | None = None,
    ) -> dict[TransitionIntent, TransitionScore]:
        """Score one (a, b) pair for every requested intent in a single compute pass.

        ``score(a, b, intent=I)`` for the four enum values produces four
        ``TransitionScore`` objects that share the same expensive parts:
        ``NeuralMixScorer.score`` (four stem compats — ~80 % of the
        cost), ``score_bpm``, ``score_energy``, and the Neural Mix
        ``best_transition`` argmax. Only the weighted ``overall`` field
        differs per intent. This bulk-scoring path computes the shared
        parts once and fans out the weighted sum across intents.

        Used by ``GeneticAlgorithm._eager_populate_cache`` to seed the
        score cache for every (idx_a, idx_b, intent) triple at ~1/4 the
        wall-clock of the per-intent loop.
        """
        targets = tuple(intents) if intents is not None else _ALL_INTENTS

        rejection = check_hard_constraints(from_t, to_t)
        if rejection is not None:
            # Hard rejects share the same TransitionScore (overall=0,
            # hard_reject=True, reject_reason set) regardless of intent.
            return {intent: rejection for intent in targets}

        nm = self._neural.score(from_t, to_t)
        bpm = score_bpm(from_t, to_t)
        energy = score_energy(from_t, to_t)
        drums = nm.stem_scores.get(NeuralMixStem.DRUMS, 0.0)
        bass = nm.stem_scores.get(NeuralMixStem.BASS, 0.0)
        harmonics = nm.stem_scores.get(NeuralMixStem.HARMONICS, 0.0)
        vocals = nm.stem_scores.get(NeuralMixStem.VOCALS, 0.0)
        best: NeuralMixTransition | None = nm.best_transition

        out: dict[TransitionIntent, TransitionScore] = {}
        for intent in targets:
            weights = INTENT_WEIGHT_MODIFIERS[intent]
            overall = (
                weights.get("bpm", 0.0) * bpm
                + weights.get("energy", 0.0) * energy
                + weights.get("drums", 0.0) * drums
                + weights.get("bass", 0.0) * bass
                + weights.get("harmonics", 0.0) * harmonics
                + weights.get("vocals", 0.0) * vocals
            )
            out[intent] = TransitionScore(
                bpm=bpm,
                energy=energy,
                drums=drums,
                bass=bass,
                harmonics=harmonics,
                vocals=vocals,
                overall=overall,
                best_transition=best,
            )
        return out

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

        # NeuralMixStem → public TransitionScore field 1:1.
        drums = nm.stem_scores.get(NeuralMixStem.DRUMS, 0.0)
        bass = nm.stem_scores.get(NeuralMixStem.BASS, 0.0)
        harmonics = nm.stem_scores.get(NeuralMixStem.HARMONICS, 0.0)
        vocals = nm.stem_scores.get(NeuralMixStem.VOCALS, 0.0)

        overall = (
            weights.get("bpm", 0.0) * bpm
            + weights.get("energy", 0.0) * energy
            + weights.get("drums", 0.0) * drums
            + weights.get("bass", 0.0) * bass
            + weights.get("harmonics", 0.0) * harmonics
            + weights.get("vocals", 0.0) * vocals
        )

        best: NeuralMixTransition | None = nm.best_transition

        return TransitionScore(
            bpm=bpm,
            energy=energy,
            drums=drums,
            bass=bass,
            harmonics=harmonics,
            vocals=vocals,
            overall=overall,
            best_transition=best,
        )
