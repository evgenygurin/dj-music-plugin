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
from app.domain.transition.weights import DEFAULT_WEIGHTS, SECTION_PAIR_OVERLAY
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

        When ``section_context`` is provided, the per-intent base weights
        are multiplied component-wise by the appropriate
        ``SECTION_PAIR_OVERLAY`` row and renormalised so the resulting
        weights still sum to 1.0. Phase 1 (v2 refactor) ships only the
        DRUM_ONLY overlay; other ``SectionPairClass`` buckets currently
        carry identity multipliers and will be calibrated in Phase 3.
        """
        rejection = check_hard_constraints(from_t, to_t)
        if rejection is not None:
            return rejection

        base_weights = INTENT_WEIGHT_MODIFIERS[intent] if intent is not None else self.weights
        weights, pair_class_value = _apply_section_overlay(base_weights, section_context)
        return self._compute_score(
            from_t,
            to_t,
            weights=weights,
            section_pair_class_value=pair_class_value,
        )

    def score_all_intents(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        intents: Iterable[TransitionIntent] | None = None,
        *,
        section_context: SectionContext | None = None,
    ) -> dict[TransitionIntent, TransitionScore]:
        """Score one (a, b) pair for every requested intent in a single compute pass.

        ``score(a, b, intent=I)`` for the four enum values produces four
        ``TransitionScore`` objects that share the same expensive parts:
        ``NeuralMixScorer.score`` (four stem compats — ~80 % of the
        cost), ``score_bpm``, ``score_energy``, and the Neural Mix
        ``best_transition`` argmax. Only the weighted ``overall`` field
        differs per intent. This bulk-scoring path computes the shared
        parts once and fans out the weighted sum across intents.

        ``section_context`` (if provided) applies the matching
        ``SECTION_PAIR_OVERLAY`` to each per-intent weight dict and
        renormalises; the overlay does not depend on intent so it can be
        resolved once outside the loop. Section pair class is the same
        for every yielded ``TransitionScore`` — it is a property of the
        pair, not of the intent.

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
            base_weights = INTENT_WEIGHT_MODIFIERS[intent]
            weights, pair_class_value = _apply_section_overlay(base_weights, section_context)
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
                section_pair_class=pair_class_value,
            )
        return out

    def score_with_candidates(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        candidate_bpm_distance: float | None = None,
        candidate_key_distance: int | None = None,
        candidate_energy_delta: float | None = None,
        *,
        section_context: SectionContext | None = None,
    ) -> TransitionScore:
        """Score reusing pre-computed candidate distances for hard checks.

        ``section_context`` is forwarded to ``_compute_score`` via the
        standard overlay+renormalise path (see ``score``). Phase 1 v2
        refactor — same semantics as ``score`` for any non-None context.
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

        weights, pair_class_value = _apply_section_overlay(self.weights, section_context)
        return self._compute_score(
            from_t,
            to_t,
            weights=weights,
            section_pair_class_value=pair_class_value,
        )

    # ── Shared internals ───────────────────────────

    def _compute_score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        weights: dict[str, float],
        section_pair_class_value: str | None = None,
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
            section_pair_class=section_pair_class_value,
        )


def _apply_section_overlay(
    base_weights: dict[str, float],
    section_context: SectionContext | None,
) -> tuple[dict[str, float], str | None]:
    """Multiply ``base_weights`` by the overlay for ``section_context``.

    Returns ``(weights, pair_class_value)`` where ``weights`` has been
    renormalised to sum to 1.0 across the six scoring components and
    ``pair_class_value`` is the string value of the resolved
    ``SectionPairClass`` (or ``None`` when no context was provided).

    With no context, returns the base weights unchanged and ``None``
    so that legacy callers see byte-identical behaviour.
    """
    if section_context is None:
        return base_weights, None

    pair_class = section_context.section_pair_class
    overlay = SECTION_PAIR_OVERLAY.get(pair_class.value)
    if overlay is None:
        # Defensive: unknown class string falls back to identity.
        return base_weights, pair_class.value

    # Multiply component-wise across the six known scoring components.
    raw: dict[str, float] = {}
    for key in ("bpm", "energy", "drums", "bass", "harmonics", "vocals"):
        raw[key] = base_weights.get(key, 0.0) * overlay.get(key, 1.0)

    total = sum(raw.values())
    if total <= 0.0:
        # Pathological: all weights collapsed to zero. Fall back to base.
        return base_weights, pair_class.value

    normalised = {key: value / total for key, value in raw.items()}
    return normalised, pair_class.value
