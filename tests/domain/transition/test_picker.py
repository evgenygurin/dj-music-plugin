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


def test_high_energy_delta_without_intent_or_hard_pair_does_not_pick_drum_cut() -> None:
    a = _track(integrated_lufs=-12.0, pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    b = _track(integrated_lufs=-8.0, pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    decision = pick_neural_mix(_ok_score(), a, b)
    assert decision.transition is not NeuralMixTransition.DRUM_CUT


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


# ── Rule 7: default ─────────────────────────────────────────────────


def test_default_picks_echo_out() -> None:
    a = _track(pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    b = _track(pitch_salience_mean=0.2, spectral_centroid_hz=1500.0)
    decision = pick_neural_mix(_ok_score(), a, b)
    assert decision.transition is NeuralMixTransition.ECHO_OUT


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
