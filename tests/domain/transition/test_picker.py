"""Tests for the Neural Mix preset picker decision tree."""

from __future__ import annotations

from app.domain.transition.intent import TransitionIntent
from app.domain.transition.neural_mix import NeuralMixTransition
from app.domain.transition.picker import (
    PickerDecision,
    build_recipe_for_pair,
    pick_neural_mix,
)
from app.domain.transition.recipe import DEFAULT_TRANSITION_BARS, NeuralMixRecipe
from app.domain.transition.score import TransitionScore
from app.domain.transition.section_context import SectionContext
from app.domain.transition.subgenre_rules import SubgenrePairType
from app.shared.constants import SectionType
from app.shared.features import TrackFeatures


def _ok_score(**kwargs: object) -> TransitionScore:
    defaults: dict[str, object] = {
        "bpm": 0.9,
        "harmonics": 0.8,
        "energy": 0.85,
        "bass": 0.8,
        "drums": 0.75,
        "vocals": 0.7,
        "overall": 0.8,
        "hard_reject": False,
        "reject_reason": None,
    }
    defaults.update(kwargs)
    return TransitionScore(**defaults)  # type: ignore[arg-type]


def _track(**kwargs: object) -> TrackFeatures:
    return TrackFeatures(**kwargs)  # type: ignore[arg-type]


# ── Rule 1: hard reject ─────────────────────────────────────────────


def test_hard_reject_routes_to_echo_out() -> None:
    score = _ok_score(hard_reject=True, reject_reason="BPM diff 14 > 10", overall=0.0)
    decision = pick_neural_mix(score, _track(), _track())
    assert decision.transition is NeuralMixTransition.ECHO_OUT
    assert "hard reject" in decision.reason.lower()
    assert decision.warnings  # non-empty


# ── Rule 2: drum-only pair ──────────────────────────────────────────


def test_drum_only_high_groove_picks_drum_swap() -> None:
    score = _ok_score(drums=0.90)
    ctx = SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)
    decision = pick_neural_mix(score, _track(), _track(), section_context=ctx)
    assert decision.transition is NeuralMixTransition.DRUM_SWAP


def test_drum_only_mid_groove_picks_drum_cut() -> None:
    score = _ok_score(drums=0.70)
    ctx = SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)
    decision = pick_neural_mix(score, _track(), _track(), section_context=ctx)
    assert decision.transition is NeuralMixTransition.DRUM_CUT


def test_drum_only_low_groove_picks_fade() -> None:
    score = _ok_score(drums=0.40)
    ctx = SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)
    decision = pick_neural_mix(score, _track(), _track(), section_context=ctx)
    assert decision.transition is NeuralMixTransition.FADE


# ── Rule 3: vocal-active outro on A ─────────────────────────────────


def test_vocal_active_a_with_vocal_low_b_picks_vocal_sustain() -> None:
    a = _track(pitch_salience_mean=0.6, spectral_centroid_hz=3000.0)
    b = _track(pitch_salience_mean=0.2, spectral_centroid_hz=1800.0)
    decision = pick_neural_mix(_ok_score(), a, b)
    assert decision.transition is NeuralMixTransition.VOCAL_SUSTAIN


def test_vocal_active_both_picks_vocal_cut() -> None:
    a = _track(pitch_salience_mean=0.6, spectral_centroid_hz=3000.0)
    b = _track(pitch_salience_mean=0.55, spectral_centroid_hz=2800.0)
    decision = pick_neural_mix(_ok_score(), a, b)
    assert decision.transition is NeuralMixTransition.VOCAL_CUT


def test_vocal_active_a_missing_b_data_picks_echo_out() -> None:
    a = _track(pitch_salience_mean=0.6, spectral_centroid_hz=3000.0)
    b = _track()  # no vocal-presence proxies
    decision = pick_neural_mix(_ok_score(), a, b)
    assert decision.transition is NeuralMixTransition.ECHO_OUT
    assert decision.warnings


# ── Rule 3 regression: acid-lead false-positive ────────────────────


def test_acid_lead_not_classified_vocal_active() -> None:
    """Acid techno (TB-303-style lead) must NOT trigger vocal-active heuristic.

    Such tracks have high pitch_salience (0.7-0.9) and high spectral_centroid
    (2500-4000 Hz) from the resonant filter peak, but their energy concentrates
    in highmid (3-7 kHz), not lowmid+mid (300-3000 Hz) where vocal formants live.

    Without the midband-ratio filter, picker would route acid → acid pairs to
    VOCAL_CUT instead of the appropriate ECHO_OUT/FADE — see
    docs/research/2026-05-13-neural-mix-transitions-deep-dive.md § 5.3.
    """
    acid_a = _track(
        pitch_salience_mean=0.85,
        spectral_centroid_hz=3200.0,
        # energy_bands order: [sub, low, lowmid, mid, highmid, high]
        # Energy concentrated in highmid (index 4): acid resonance peak.
        energy_bands=[0.05, 0.10, 0.08, 0.07, 0.45, 0.25],
    )
    acid_b = _track(
        pitch_salience_mean=0.78,
        spectral_centroid_hz=2900.0,
        energy_bands=[0.05, 0.10, 0.10, 0.08, 0.42, 0.25],
    )
    score = _ok_score()

    decision = pick_neural_mix(score, acid_a, acid_b)

    assert decision.transition is not NeuralMixTransition.VOCAL_CUT, (
        f"acid pair routed to VOCAL_CUT (false positive). "
        f"Decision: {decision.transition.value}, reason: {decision.reason}"
    )
    assert decision.transition is not NeuralMixTransition.VOCAL_SUSTAIN, (
        "acid pair must not route to VOCAL_SUSTAIN either"
    )


def test_real_vocal_track_classified_vocal_active() -> None:
    """Positive case: vocal track with concentrated midband energy passes the heuristic.

    Lead vocal has pitch_salience > 0.55, centroid in vocal range (2-3 kHz),
    AND energy concentrated in lowmid+mid = 300-3000 Hz (formant band).
    """
    vocal_a = _track(
        pitch_salience_mean=0.70,
        spectral_centroid_hz=2500.0,
        # Energy concentrated in lowmid+mid: typical vocal formant distribution.
        energy_bands=[0.05, 0.10, 0.25, 0.30, 0.20, 0.10],
    )
    vocal_b = _track(
        pitch_salience_mean=0.65,
        spectral_centroid_hz=2400.0,
        energy_bands=[0.05, 0.10, 0.28, 0.27, 0.20, 0.10],
    )
    score = _ok_score()

    decision = pick_neural_mix(score, vocal_a, vocal_b)

    assert decision.transition is NeuralMixTransition.VOCAL_CUT, (
        f"two vocal-active tracks should still route to VOCAL_CUT "
        f"(rule 3). Got: {decision.transition.value}"
    )


def test_vocal_active_pitch_salience_below_new_threshold() -> None:
    """Track with pitch_salience = 0.54 (just below 0.55 threshold) is NOT vocal-active.

    Guards against regression if the threshold is loosened back toward 0.4.
    """
    boundary = _track(
        pitch_salience_mean=0.54,
        spectral_centroid_hz=3000.0,
        energy_bands=[0.05, 0.10, 0.25, 0.25, 0.25, 0.10],  # vocal-like distribution
    )
    other = _track(
        pitch_salience_mean=0.20,
        spectral_centroid_hz=1800.0,
        energy_bands=[0.10, 0.20, 0.25, 0.25, 0.15, 0.05],
    )
    score = _ok_score()

    decision = pick_neural_mix(score, boundary, other)

    # Rule 3 should NOT fire (pitch_salience below new threshold).
    # Decision falls through to rule 4/6/7 — exact result depends on other
    # signals; we only assert rule 3 didn't trigger.
    assert decision.transition not in {
        NeuralMixTransition.VOCAL_CUT,
        NeuralMixTransition.VOCAL_SUSTAIN,
    }, (
        f"pitch_salience 0.54 (below 0.55 threshold) must not trigger rule 3. "
        f"Got: {decision.transition.value}, reason: {decision.reason}"
    )


def test_vocal_active_fallback_without_energy_bands() -> None:
    """Legacy rows without energy_bands must still work via 2-signal fallback.

    Older L1/L2 features may have pitch_salience + centroid but missing
    energy_bands (the column was added later in the pipeline). The midband
    gate must degrade gracefully and not reject these rows.
    """
    legacy_vocal = _track(
        pitch_salience_mean=0.65,
        spectral_centroid_hz=2400.0,
        energy_bands=None,  # legacy: no band breakdown
    )
    other_vocal = _track(
        pitch_salience_mean=0.60,
        spectral_centroid_hz=2500.0,
        energy_bands=None,
    )
    score = _ok_score()

    decision = pick_neural_mix(score, legacy_vocal, other_vocal)

    # Both pass 2-signal check → rule 3 fires → VOCAL_CUT (both vocal-active).
    assert decision.transition is NeuralMixTransition.VOCAL_CUT, (
        f"legacy 2-signal vocal pair must still route to VOCAL_CUT. "
        f"Got: {decision.transition.value}"
    )


def test_vocal_active_handles_short_energy_bands() -> None:
    """Malformed energy_bands (fewer than 6 elements) falls back to 2-signal check.

    Defensive: if a future pipeline change produces incomplete bands,
    picker must not crash with IndexError.
    """
    weird = _track(
        pitch_salience_mean=0.70,
        spectral_centroid_hz=2600.0,
        energy_bands=[0.5, 0.5],  # only 2 bands instead of 6
    )
    other = _track(
        pitch_salience_mean=0.65,
        spectral_centroid_hz=2400.0,
        energy_bands=None,
    )
    score = _ok_score()

    # Must not raise.
    decision = pick_neural_mix(score, weird, other)

    # Both treated as vocal-active via 2-signal fallback (len check guards midband).
    assert decision.transition is NeuralMixTransition.VOCAL_CUT


# ── Rule 4: harmonic motif on A ─────────────────────────────────────


def test_harmonic_motif_a_with_compatible_key_and_vocal_low_b() -> None:
    a = _track(
        pitch_salience_mean=0.25,
        spectral_centroid_hz=1500.0,
        tonnetz_vector=[0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
        key_code=14,
    )
    b = _track(
        pitch_salience_mean=0.2,
        spectral_centroid_hz=1500.0,
        key_code=14,
    )
    decision = pick_neural_mix(_ok_score(), a, b)
    assert decision.transition is NeuralMixTransition.HARMONIC_SUSTAIN


def test_harmonic_motif_a_with_incompatible_key_does_not_pick_harmonic_sustain() -> None:
    a = _track(
        pitch_salience_mean=0.25,
        spectral_centroid_hz=1500.0,
        tonnetz_vector=[0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
        key_code=0,
    )
    b = _track(pitch_salience_mean=0.2, spectral_centroid_hz=1500.0, key_code=8)
    decision = pick_neural_mix(_ok_score(), a, b)
    assert decision.transition is not NeuralMixTransition.HARMONIC_SUSTAIN


# ── Rule 5: energy delta + ramp-up / hard pair ──────────────────────


def test_high_energy_delta_with_ramp_up_intent_picks_drum_cut() -> None:
    a = _track(integrated_lufs=-12.0, pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    b = _track(integrated_lufs=-8.0, pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    decision = pick_neural_mix(_ok_score(), a, b, intent=TransitionIntent.RAMP_UP)
    assert decision.transition is NeuralMixTransition.DRUM_CUT


def test_high_energy_delta_with_hard_pair_picks_drum_cut() -> None:
    a = _track(integrated_lufs=-12.0, pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    b = _track(integrated_lufs=-8.0, pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    decision = pick_neural_mix(
        _ok_score(),
        a,
        b,
        subgenre_pair=SubgenrePairType.HARD_PAIR,
    )
    assert decision.transition is NeuralMixTransition.DRUM_CUT


def test_high_energy_delta_in_default_picks_drum_cut() -> None:
    """Energy lift (>2 LUFS) with locked drums → DRUM_CUT even without an
    explicit RAMP_UP intent: the drum-driven default reads energy direction.

    (Pre-fix this fell through to ECHO_OUT.)
    """
    a = _track(integrated_lufs=-12.0, pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    b = _track(integrated_lufs=-8.0, pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    decision = pick_neural_mix(_ok_score(), a, b)
    assert decision.transition is NeuralMixTransition.DRUM_CUT


# ── Rule 6: ambient pair / cool-down ────────────────────────────────


def test_ambient_pair_picks_fade() -> None:
    a = _track(pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    b = _track(pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    decision = pick_neural_mix(
        _ok_score(),
        a,
        b,
        subgenre_pair=SubgenrePairType.AMBIENT_PAIR,
    )
    assert decision.transition is NeuralMixTransition.FADE


def test_cool_down_intent_picks_fade() -> None:
    a = _track(pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    b = _track(pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    decision = pick_neural_mix(_ok_score(), a, b, intent=TransitionIntent.COOL_DOWN)
    assert decision.transition is NeuralMixTransition.FADE


# ── Rule 7: smooth full-stem blend ──────────────────────────────────


def test_balanced_energy_stable_pair_picks_fade() -> None:
    """When every routed stem is compatible and LUFS is stable, use the
    transparent crossfade instead of forcing another drum swap."""
    a = _track(integrated_lufs=-9.2, pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    b = _track(integrated_lufs=-8.8, pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    decision = pick_neural_mix(
        _ok_score(
            drums=0.77,
            bass=0.78,
            harmonics=0.80,
            vocals=0.74,
            overall=0.79,
        ),
        a,
        b,
    )
    assert decision.transition is NeuralMixTransition.FADE


def test_balanced_pair_with_energy_lift_still_picks_drum_cut() -> None:
    """A +4 LUFS lift is a drop, not a transparent blend."""
    a = _track(integrated_lufs=-12.0, pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    b = _track(integrated_lufs=-8.0, pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    decision = pick_neural_mix(
        _ok_score(
            drums=0.77,
            bass=0.78,
            harmonics=0.80,
            vocals=0.74,
            overall=0.79,
        ),
        a,
        b,
    )
    assert decision.transition is NeuralMixTransition.DRUM_CUT


# ── Rule 8: melodic / hypnotic harmonic continuity ─────────────────


def test_hypnotic_tonal_pair_picks_harmonic_sustain_before_drum_swap() -> None:
    a = _track(
        key_code=14,
        pitch_salience_mean=0.40,  # above strict motif threshold
        spectral_centroid_hz=1700.0,
    )
    b = _track(
        key_code=14,
        pitch_salience_mean=0.24,
        spectral_centroid_hz=1600.0,
    )
    decision = pick_neural_mix(
        _ok_score(
            drums=0.70,
            bass=0.72,
            harmonics=0.86,
            vocals=0.58,
            overall=0.78,
        ),
        a,
        b,
        subgenre_pair=SubgenrePairType.HYPNOTIC_PAIR,
    )
    assert decision.transition is NeuralMixTransition.HARMONIC_SUSTAIN


def test_harmonic_continuity_requires_compatible_key() -> None:
    a = _track(
        key_code=0,
        pitch_salience_mean=0.40,
        spectral_centroid_hz=1700.0,
    )
    b = _track(
        key_code=8,
        pitch_salience_mean=0.24,
        spectral_centroid_hz=1600.0,
    )
    decision = pick_neural_mix(
        _ok_score(
            drums=0.70,
            bass=0.72,
            harmonics=0.86,
            vocals=0.58,
            overall=0.78,
        ),
        a,
        b,
        subgenre_pair=SubgenrePairType.HYPNOTIC_PAIR,
    )
    assert decision.transition is NeuralMixTransition.DRUM_SWAP


# ── Rule 9: drum-driven default ─────────────────────────────────────


def test_default_drum_driven_picks_drum_swap() -> None:
    """Instrumental techno, locked drums, no energy lift → DRUM_SWAP
    (canonical long EQ-swap blend), NOT echo_out. This is the core fix:
    techno is mixed on the drums, so the blanket ECHO_OUT default was wrong.
    """
    a = _track(pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    b = _track(pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    decision = pick_neural_mix(_ok_score(), a, b)
    assert decision.transition is NeuralMixTransition.DRUM_SWAP


def test_mid_drums_picks_drum_cut() -> None:
    """Partial groove lock (0.45 <= drums < 0.62) → DRUM_CUT — a clean quick
    swap beats a muddy blend."""
    a = _track(pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    b = _track(pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    decision = pick_neural_mix(_ok_score(drums=0.50), a, b)
    assert decision.transition is NeuralMixTransition.DRUM_CUT


def test_low_drums_picks_echo_out_rescue() -> None:
    """Groove mismatch (drums < 0.45) → ECHO_OUT echo-tail rescue.

    ECHO_OUT survives ONLY as a rescue now, not the blanket default.
    """
    a = _track(pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    b = _track(pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    decision = pick_neural_mix(_ok_score(drums=0.30), a, b)
    assert decision.transition is NeuralMixTransition.ECHO_OUT
    assert "rescue" in decision.reason.lower()


# ── Decision shape ──────────────────────────────────────────────────


def test_decision_has_confidence_and_reason() -> None:
    decision = pick_neural_mix(_ok_score(), _track(), _track())
    assert isinstance(decision, PickerDecision)
    assert 0.0 <= decision.confidence <= 1.0
    assert decision.reason


# ── build_recipe_for_pair convenience wrapper ───────────────────────


def test_build_recipe_for_pair_returns_full_recipe() -> None:
    a = _track(pitch_salience_mean=0.6, spectral_centroid_hz=3000.0)
    b = _track(pitch_salience_mean=0.2, spectral_centroid_hz=1800.0)
    recipe = build_recipe_for_pair(_ok_score(), a, b)
    assert isinstance(recipe, NeuralMixRecipe)
    assert recipe.transition is NeuralMixTransition.VOCAL_SUSTAIN
    assert recipe.bars == DEFAULT_TRANSITION_BARS
    assert recipe.keyframes
    assert recipe.explanation
    assert recipe.confidence > 0.5


def test_build_recipe_for_pair_clamps_bars_for_hard_pair() -> None:
    a = _track(integrated_lufs=-12.0, pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    b = _track(integrated_lufs=-8.0, pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    recipe = build_recipe_for_pair(
        _ok_score(),
        a,
        b,
        subgenre_pair=SubgenrePairType.HARD_PAIR,
        intent=TransitionIntent.RAMP_UP,
    )
    # HARD_PAIR clamp ceiling is 16 — 32-bar default is reduced.
    assert recipe.bars <= 16


def test_build_recipe_for_pair_records_section_labels() -> None:
    a = _track(pitch_salience_mean=0.6, spectral_centroid_hz=3000.0)
    b = _track(pitch_salience_mean=0.2, spectral_centroid_hz=1800.0)
    ctx = SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)
    recipe = build_recipe_for_pair(_ok_score(drums=0.40), a, b, section_context=ctx)
    assert recipe.mix_out_section == "outro"
    assert recipe.mix_in_section == "intro"


def test_hypnotic_pair_falls_through_to_default_drum_swap() -> None:
    score = _ok_score()
    decision = pick_neural_mix(
        score, _track(), _track(), subgenre_pair=SubgenrePairType.HYPNOTIC_PAIR
    )
    assert decision.transition is NeuralMixTransition.DRUM_SWAP


def test_hypnotic_pair_recipe_uses_standard_preset() -> None:
    recipe = build_recipe_for_pair(
        _ok_score(),
        _track(),
        _track(),
        subgenre_pair=SubgenrePairType.HYPNOTIC_PAIR,
    )
    assert recipe.transition is NeuralMixTransition.DRUM_SWAP
