"""Tests for Neural Mix preset builders (7 djay Pro 5 + FILTER_SWEEP extension)."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from app.domain.transition.builders import (
    build_drum_cut,
    build_drum_swap,
    build_echo_out,
    build_fade,
    build_filter_sweep,
    build_harmonic_sustain,
    build_recipe,
    build_vocal_cut,
    build_vocal_sustain,
)
from app.domain.transition.neural_mix import NeuralMixStem, NeuralMixTransition
from app.domain.transition.recipe import (
    DEFAULT_TRANSITION_BARS,
    LEVEL_SILENT,
    LEVEL_UNITY,
    MuteFXTrigger,
    NeuralMixRecipe,
    StemKeyframe,
)

ALL_BUILDERS = (
    (NeuralMixTransition.FADE, build_fade),
    (NeuralMixTransition.ECHO_OUT, build_echo_out),
    (NeuralMixTransition.VOCAL_SUSTAIN, build_vocal_sustain),
    (NeuralMixTransition.HARMONIC_SUSTAIN, build_harmonic_sustain),
    (NeuralMixTransition.DRUM_SWAP, build_drum_swap),
    (NeuralMixTransition.VOCAL_CUT, build_vocal_cut),
    (NeuralMixTransition.DRUM_CUT, build_drum_cut),
    (NeuralMixTransition.FILTER_SWEEP, build_filter_sweep),
)


def _channel(
    keyframes: Iterable[StemKeyframe], deck: str, stem: NeuralMixStem
) -> list[StemKeyframe]:
    return sorted(
        (kf for kf in keyframes if kf.deck == deck and kf.stem is stem),
        key=lambda kf: kf.bar,
    )


# ── Cross-preset invariants ─────────────────────────────────────────


@pytest.mark.parametrize(("transition", "builder"), ALL_BUILDERS)
def test_builder_default_bars_is_32(transition: NeuralMixTransition, builder: object) -> None:
    keyframes, _fx = builder()  # type: ignore[operator]
    # All keyframes fall within [0, 32].
    for kf in keyframes:
        assert 0.0 <= kf.bar <= float(DEFAULT_TRANSITION_BARS), (
            f"{transition} keyframe at bar {kf.bar} outside [0, 32]"
        )


@pytest.mark.parametrize(("transition", "builder"), ALL_BUILDERS)
def test_builder_covers_all_eight_channels(
    transition: NeuralMixTransition, builder: object
) -> None:
    """Every (deck, stem) channel must have at least one keyframe."""
    keyframes, _fx = builder()  # type: ignore[operator]
    channels = {(kf.deck, kf.stem) for kf in keyframes}
    expected = {(deck, stem) for deck in ("A", "B") for stem in NeuralMixStem}
    assert channels == expected, f"{transition} missing channels: {expected - channels}"


@pytest.mark.parametrize(("transition", "builder"), ALL_BUILDERS)
def test_builder_levels_within_silence_floor(
    transition: NeuralMixTransition, builder: object
) -> None:
    keyframes, _fx = builder()  # type: ignore[operator]
    for kf in keyframes:
        assert LEVEL_SILENT <= kf.level_db <= LEVEL_UNITY, (
            f"{transition} keyframe level {kf.level_db} outside [{LEVEL_SILENT}, {LEVEL_UNITY}]"
        )


@pytest.mark.parametrize(("transition", "builder"), ALL_BUILDERS)
def test_builder_starts_a_at_unity_and_b_at_silent(
    transition: NeuralMixTransition, builder: object
) -> None:
    """Bar 0 must have A at unity and B at silent for every stem."""
    keyframes, _fx = builder()  # type: ignore[operator]
    for stem in NeuralMixStem:
        a = _channel(keyframes, "A", stem)
        b = _channel(keyframes, "B", stem)
        assert a, f"{transition} A.{stem} has no keyframes"
        assert b, f"{transition} B.{stem} has no keyframes"
        assert a[0].level_db == LEVEL_UNITY, (
            f"{transition} A.{stem} should start at 0 dB, got {a[0].level_db}"
        )
        assert b[0].level_db == LEVEL_SILENT, (
            f"{transition} B.{stem} should start silent, got {b[0].level_db}"
        )


@pytest.mark.parametrize(("transition", "builder"), ALL_BUILDERS)
def test_builder_ends_a_silent_and_b_at_unity(
    transition: NeuralMixTransition, builder: object
) -> None:
    """End of transition: A must be silent on every stem, B at unity."""
    keyframes, _fx = builder()  # type: ignore[operator]
    for stem in NeuralMixStem:
        a = _channel(keyframes, "A", stem)
        b = _channel(keyframes, "B", stem)
        assert a[-1].level_db == LEVEL_SILENT, (
            f"{transition} A.{stem} should end silent, got {a[-1].level_db}"
        )
        assert b[-1].level_db == LEVEL_UNITY, (
            f"{transition} B.{stem} should end at 0 dB, got {b[-1].level_db}"
        )


# ── Per-preset characteristic checks ────────────────────────────────


def test_fade_has_no_fx_events() -> None:
    _kfs, fx = build_fade()
    assert fx == ()


def test_fade_is_monotone_per_channel() -> None:
    """For FADE every channel ramps strictly toward its target — A ↘, B ↗."""
    keyframes, _fx = build_fade()
    for stem in NeuralMixStem:
        a_levels = [kf.level_db for kf in _channel(keyframes, "A", stem)]
        b_levels = [kf.level_db for kf in _channel(keyframes, "B", stem)]
        assert a_levels == sorted(a_levels, reverse=True), f"A.{stem} not monotone ↘"
        assert b_levels == sorted(b_levels), f"B.{stem} not monotone ↗"


def test_echo_out_kills_vocals_first_then_harmonic_then_drums() -> None:
    _keyframes, fx = build_echo_out()
    triggers = {(ev.stem, ev.trigger) for ev in fx}
    # All four A stems get an echo_3_4 tail trigger.
    for stem in NeuralMixStem:
        assert (stem, MuteFXTrigger.ECHO_3_4) in triggers, f"{stem} missing echo_3_4 trigger"

    # Sequencing: vocals < harmonics < drums (in absolute bar position).
    by_stem = {ev.stem: ev.bar for ev in fx}
    assert (
        by_stem[NeuralMixStem.VOCALS]
        < by_stem[NeuralMixStem.HARMONICS]
        < by_stem[NeuralMixStem.DRUMS]
    )


def test_vocal_sustain_holds_a_vocals_past_three_quarters() -> None:
    keyframes, _fx = build_vocal_sustain()
    a_vocals = _channel(keyframes, "A", NeuralMixStem.VOCALS)
    # A.vocals stays at unity until at least bar 24 (3/4 of 32).
    at_24 = [kf for kf in a_vocals if kf.bar >= 24.0 and kf.level_db == LEVEL_UNITY]
    assert at_24, "A.vocals should still be at 0 dB at bar 24"


def test_harmonic_sustain_holds_a_harmonic_past_three_quarters() -> None:
    keyframes, _fx = build_harmonic_sustain()
    a_h = _channel(keyframes, "A", NeuralMixStem.HARMONICS)
    at_24 = [kf for kf in a_h if kf.bar >= 24.0 and kf.level_db == LEVEL_UNITY]
    assert at_24, "A.harmonic should still be at 0 dB at bar 24"


def test_drum_swap_phase_one_only_swaps_drums() -> None:
    """At bar 16 (mid-point) drums fully swapped, other stems still on A."""
    keyframes, _fx = build_drum_swap()
    # At bar 16, A.drums is silent and B.drums is at unity.
    a_drums = _channel(keyframes, "A", NeuralMixStem.DRUMS)
    b_drums = _channel(keyframes, "B", NeuralMixStem.DRUMS)
    a_at_16 = next(kf for kf in a_drums if kf.bar == 16.0)
    b_at_16 = next(kf for kf in b_drums if kf.bar == 16.0)
    assert a_at_16.level_db == LEVEL_SILENT
    assert b_at_16.level_db == LEVEL_UNITY

    # Other stems still on A at bar 16.
    for stem in (NeuralMixStem.BASS, NeuralMixStem.HARMONICS, NeuralMixStem.VOCALS):
        a_other = _channel(keyframes, "A", stem)
        a_other_at_16 = next(kf for kf in a_other if kf.bar == 16.0)
        assert a_other_at_16.level_db == LEVEL_UNITY, (
            f"A.{stem} should still be at 0 dB at bar 16 (phase 1)"
        )


def test_vocal_cut_kills_a_vocals_with_echo_1_2() -> None:
    keyframes, fx = build_vocal_cut()
    assert any(
        ev.stem is NeuralMixStem.VOCALS and ev.trigger is MuteFXTrigger.ECHO_1_2 for ev in fx
    )
    # A.vocals reaches LEVEL_SILENT early (within first ⅛, i.e. ≤ bar 4 on a 32-bar transition).
    a_vocals = _channel(keyframes, "A", NeuralMixStem.VOCALS)
    silent_kfs = [kf for kf in a_vocals if kf.level_db == LEVEL_SILENT]
    assert silent_kfs and silent_kfs[0].bar <= 4.0


def test_drum_cut_kills_a_drums_with_echo_1_2() -> None:
    keyframes, fx = build_drum_cut()
    assert any(
        ev.stem is NeuralMixStem.DRUMS and ev.trigger is MuteFXTrigger.ECHO_1_2 for ev in fx
    )
    a_drums = _channel(keyframes, "A", NeuralMixStem.DRUMS)
    silent_kfs = [kf for kf in a_drums if kf.level_db == LEVEL_SILENT]
    assert silent_kfs and silent_kfs[0].bar <= 4.0


def test_drum_cut_b_drums_slam_at_end() -> None:
    """B.drums must stay silent until very late, then ramp to 0 dB by bar 32."""
    keyframes, _fx = build_drum_cut()
    b_drums = _channel(keyframes, "B", NeuralMixStem.DRUMS)
    # The silent run must extend past bar 24 (otherwise it's not a slam, it's a fade).
    silent_kfs = [kf for kf in b_drums if kf.level_db == LEVEL_SILENT]
    assert silent_kfs and max(kf.bar for kf in silent_kfs) >= 24.0
    # And must reach 0 dB by bar 32.
    assert b_drums[-1].level_db == LEVEL_UNITY
    assert b_drums[-1].bar == 32.0


# ── Public dispatcher ───────────────────────────────────────────────


@pytest.mark.parametrize("transition", list(NeuralMixTransition))
def test_build_recipe_for_every_transition(transition: NeuralMixTransition) -> None:
    recipe = build_recipe(transition)
    assert isinstance(recipe, NeuralMixRecipe)
    assert recipe.transition is transition
    assert recipe.bars == DEFAULT_TRANSITION_BARS
    assert recipe.keyframes


def test_build_recipe_respects_custom_bars() -> None:
    recipe = build_recipe(NeuralMixTransition.FADE, bars=64)
    assert recipe.bars == 64
    assert max(kf.bar for kf in recipe.keyframes) == 64.0


def test_build_recipe_rejects_non_positive_bars() -> None:
    with pytest.raises(ValueError, match="positive"):
        build_recipe(NeuralMixTransition.FADE, bars=0)


def test_build_recipe_round_trips_through_json() -> None:
    recipe = build_recipe(
        NeuralMixTransition.DRUM_CUT,
        confidence=0.9,
        rescue=NeuralMixTransition.ECHO_OUT,
        explanation="strong ramp-up",
        warnings=("drumless window",),
    )
    parsed = NeuralMixRecipe.from_json(recipe.to_json())
    assert parsed == recipe


# ── FILTER_SWEEP specific ───────────────────────────────────────────


def test_filter_sweep_a_bass_exits_first() -> None:
    """A.bass must be silent by bar 8 (¼ of 32) — earlier than other A stems."""
    keyframes, _fx = build_filter_sweep()
    a_bass = _channel(keyframes, "A", NeuralMixStem.BASS)
    silent_kfs = [kf for kf in a_bass if kf.level_db == LEVEL_SILENT]
    assert silent_kfs, "A.bass must reach LEVEL_SILENT"
    assert silent_kfs[0].bar <= 8.0, "A.bass should be silent by ¼ of 32 bars"


def test_filter_sweep_b_bass_enters_last() -> None:
    """B.bass must be at 0 dB only at the end — entering after other B stems."""
    keyframes, _fx = build_filter_sweep()
    b_bass = _channel(keyframes, "B", NeuralMixStem.BASS)
    # Must be silent for most of the transition.
    silent_kfs = [kf for kf in b_bass if kf.level_db == LEVEL_SILENT]
    assert silent_kfs and max(kf.bar for kf in silent_kfs) >= 20.0
    # Must reach 0 dB by the end.
    assert b_bass[-1].level_db == LEVEL_UNITY
    assert b_bass[-1].bar == float(DEFAULT_TRANSITION_BARS)


def test_filter_sweep_no_fx_events() -> None:
    """FILTER_SWEEP is a smooth blend — no abrupt echo-tail triggers."""
    _keyframes, fx = build_filter_sweep()
    assert fx == (), "FILTER_SWEEP should produce no MuteFX events"


def test_filter_sweep_b_drums_enter_before_b_bass() -> None:
    """B.drums arrive before B.bass — drums/harmonic bed established first."""
    keyframes, _fx = build_filter_sweep()
    b_bass = _channel(keyframes, "B", NeuralMixStem.BASS)
    b_drums = _channel(keyframes, "B", NeuralMixStem.DRUMS)
    # B.drums must reach 0 dB before B.bass does.
    b_drums_unity_bar = next(kf.bar for kf in b_drums if kf.level_db == LEVEL_UNITY)
    b_bass_unity_bar = next(kf.bar for kf in b_bass if kf.level_db == LEVEL_UNITY)
    assert b_drums_unity_bar < b_bass_unity_bar
