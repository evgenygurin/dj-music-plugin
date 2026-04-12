"""Transition style recommendation.

Decoupled from the scorer engine: ``recommend_style`` is a pure
function on a ``TransitionScore``, so it can be called on a synthetic
score reconstructed from a persisted DB row (see
``app/services/set/scoring.py``) without rebuilding the scorer.

The decision tree thresholds live in a ``StyleRules`` dataclass
(``app/transition/weights.py``) so future per-template overrides
can swap them without touching this module.

Decision tree (in priority order):
  1. Hard reject              → FILTER_SWEEP    (last resort, requires
                                                 spectral cleanup before
                                                 the swap is even safe)
  2. score.spectral < cutoff  → FILTER_SWEEP    (spectral collision —
                                                 sweep outgoing HPF up)
  3. score.energy   < cutoff  → ECHO_OUT        (big energy gap —
                                                 tail-stop with echo)
  4. score.harmonic < cutoff  → LONG_BLEND      (key drift — slow
                                                 harmonic shift)
  5. score.bpm    > perfect
     AND score.harmonic > perfect
     AND score.groove   > perfect → CUT          (perfect match — drop
                                                 on the bar, no overlap)
  6. score.overall > confident → BASS_SWAP_SHORT (good match — 8 bars)
  7. else                     → BASS_SWAP_LONG  (DJ default — 32 bars)
"""

from __future__ import annotations

from typing import Any

from dj_music.core.constants import TRANSITION_STYLE_PROFILES, TransitionStyle
from dj_music.schemas.audio import TrackFeatures
from dj_music.transition.recipe import DjayTransition, EQPlan, TransitionRecipe, TransitionType
from dj_music.transition.score import TransitionScore
from dj_music.transition.weights import DEFAULT_STYLE_RULES, StyleRules


def recommend_style(
    score: TransitionScore,
    *,
    rules: StyleRules = DEFAULT_STYLE_RULES,
) -> TransitionStyle:
    """Pick a transition style from a 6-component score.

    Pure function — no I/O, no DB, no engine state. Decisions are based
    only on the public fields of ``TransitionScore`` and the cutoffs in
    ``rules``. ``rules`` defaults to the historical hand-tuned values;
    pass a custom ``StyleRules`` to override per-template.

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
    if score.spectral < rules.spectral_collision_cutoff:
        return TransitionStyle.FILTER_SWEEP

    # Energy gap → echo-tail the outgoing track to bridge the drop.
    # Long blends across an energy chasm just sound like a slow
    # disappointment.
    if score.energy < rules.energy_gap_cutoff:
        return TransitionStyle.ECHO_OUT

    # Harmonic mismatch → long tonal blend gives the ear time to
    # accept the new key. Camelot wheel is forgiving but not
    # instantaneous.
    if score.harmonic < rules.harmonic_drift_cutoff:
        return TransitionStyle.LONG_BLEND

    # Near-perfect match across BPM, key, and groove → just cut on
    # the bar. Crossfading a perfectly aligned pair is busy-work.
    if (
        score.bpm > rules.perfect_bpm_cutoff
        and score.harmonic > rules.perfect_harmonic_cutoff
        and score.groove > rules.perfect_groove_cutoff
    ):
        return TransitionStyle.CUT

    # Default branches: short or long bass-swap blend depending on
    # how confident we are in the overall fit.
    if score.overall > rules.confident_overall_cutoff:
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


def recommend_recipe(
    score: TransitionScore,
    features_a: TrackFeatures | None = None,
    features_b: TrackFeatures | None = None,
    **kwargs: Any,
) -> TransitionRecipe:
    """Generate full transition recipe. Falls back to style-based if no features."""
    if features_a is not None and features_b is not None:
        from dj_music.transition.recipe_engine import TransitionRecipeEngine

        engine = TransitionRecipeEngine()
        return engine.generate(score, features_a, features_b, **kwargs)
    # Fallback: convert old style to basic recipe
    style = recommend_style(score)
    profile = style_profile(style)
    return TransitionRecipe(
        transition_type=TransitionType(style.value),
        bars=int(profile["bars"]),
        djay_transition=DjayTransition.NONE,
        djay_tempo_adjust="sync",
        steps=(),
        eq_plan=EQPlan(low="keep", mid="keep", high="keep"),
        mix_in_section=None,
        mix_out_section=None,
        phrase_align=True,
        warnings=(),
        confidence=0.5,
        subgenre_modifier=None,
        rescue_move="filter sweep + hard cut",
    )
