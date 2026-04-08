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

from app.core.constants import (
    DEFAULT_TRANSITION_WEIGHTS,
    TRANSITION_STYLE_PROFILES,
    TransitionStyle,
)
from app.core.track_features import TrackFeatures
from app.core.transition_intent import INTENT_WEIGHT_MODIFIERS, TransitionIntent
from app.domain.transition.components import (
    score_bpm,
    score_energy,
    score_groove,
    score_harmonic,
    score_spectral,
    score_timbral,
)
from app.domain.transition.hard_constraints import check_hard_constraints
from app.domain.transition.score import TransitionScore

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
    ) -> TransitionScore:
        """Compute the full 6-component score.

        Args:
            from_t: Features of the outgoing track.
            to_t: Features of the incoming track.
            intent: Optional context-aware intent for weight modifiers.
                When provided, per-intent weights override instance defaults.
        """
        rejection = check_hard_constraints(from_t, to_t)
        if rejection is not None:
            return rejection

        weights = INTENT_WEIGHT_MODIFIERS[intent] if intent is not None else None
        return self._compute_score(from_t, to_t, weights=weights)

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
    ) -> TransitionScore:
        """Run all 6 component functions and combine them with weights."""
        w = weights or self.weights
        bpm = score_bpm(from_t, to_t)
        harmonic = score_harmonic(from_t, to_t)
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


# ── Style recommendation ─────────────────────────────────────────────
#
# Decoupled from the scorer class so it can be called on a cached
# `TransitionScore` without rebuilding the engine.
#
# Decision tree (in priority order):
#   1. Hard reject              → FILTER_SWEEP    (last resort, requires
#                                                  spectral cleanup before
#                                                  the swap is even safe)
#   2. score.spectral < 0.45    → FILTER_SWEEP    (spectral collision —
#                                                  sweep outgoing HPF up)
#   3. score.energy < 0.40      → ECHO_OUT        (big energy gap —
#                                                  tail-stop with echo)
#   4. score.harmonic < 0.55    → LONG_BLEND      (key drift — slow
#                                                  harmonic shift)
#   5. score.bpm    > 0.95
#      AND score.harmonic > 0.85
#      AND score.groove   > 0.75 → CUT             (perfect match — drop
#                                                  on the bar, no overlap)
#   6. score.overall > 0.75     → BASS_SWAP_SHORT (good match — 8 bars)
#   7. else                     → BASS_SWAP_LONG  (DJ default — 32 bars)


def recommend_style(score: TransitionScore) -> TransitionStyle:
    """Pick a transition style from a 6-component score.

    Pure function — no I/O, no DB, no engine state. Decisions are based
    only on the public fields of ``TransitionScore``. The thresholds
    encode the rules in the comment block above.

    A hard-rejected score still returns a style (FILTER_SWEEP) — it is
    the *caller's* job to decide whether to actually play the
    transition. ``recommend_style`` only answers "if you do play it,
    here's the least bad way to do it".
    """
    if score.hard_reject:
        return TransitionStyle.FILTER_SWEEP

    # Spectral collision → sweep before anything else, even if other
    # axes are clean. Two tracks fighting for the same frequency band
    # can't be solved with a longer crossfade.
    if score.spectral < 0.45:
        return TransitionStyle.FILTER_SWEEP

    # Energy gap → echo-tail the outgoing track to bridge the drop.
    # Long blends across an energy chasm just sound like a slow
    # disappointment.
    if score.energy < 0.40:
        return TransitionStyle.ECHO_OUT

    # Harmonic mismatch → long tonal blend gives the ear time to
    # accept the new key. Camelot wheel is forgiving but not
    # instantaneous.
    if score.harmonic < 0.55:
        return TransitionStyle.LONG_BLEND

    # Near-perfect match across BPM, key, and groove → just cut on
    # the bar. Crossfading a perfectly aligned pair is busy-work.
    if score.bpm > 0.95 and score.harmonic > 0.85 and score.groove > 0.75:
        return TransitionStyle.CUT

    # Default branches: short or long bass-swap blend depending on
    # how confident we are in the overall fit.
    if score.overall > 0.75:
        return TransitionStyle.BASS_SWAP_SHORT
    return TransitionStyle.BASS_SWAP_LONG


def style_profile(style: TransitionStyle) -> dict[str, float | str]:
    """Return the bars + reason metadata for a given style.

    Thin wrapper around ``TRANSITION_STYLE_PROFILES`` so callers don't
    need to import the table directly. Raises ``KeyError`` for unknown
    styles, which would only happen if the enum and table drift apart
    (covered by tests).
    """
    return TRANSITION_STYLE_PROFILES[style]
