"""Tests for the core tempo / beatgrid types.

Pure-dataclass + numpy-only — no librosa, no audio fixtures, fully
deterministic. The tests pin invariants the render layer relies on:

* downbeats/bars are derived correctly from a beat sequence
* phase is in [0, beat_period)
* tempo_curve windows agree with the full-track median
* hypothesis octave-resolution prefers the 1x when no hint is given
* phrase boundaries snap to powers of two
"""

from __future__ import annotations

import pytest

from app.audio.core.tempo import (
    TempoCurvePoint,
    TempoHypothesis,
    beatgrid_from_arrays,
    derive_phrase_boundaries,
    downbeats_from_beats,
    is_multiple_of_bpm,
    phase_from_first_beat,
    resolve_octave,
    round_bpm,
    tempo_curve_from_beat_times,
)

# ── downbeats / bars ─────────────────────────────────────────────────


def test_downbeats_from_beats_splits_on_bar_boundary() -> None:
    beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
    downbeats, bars = downbeats_from_beats(beats, beats_per_bar=4)
    assert downbeats == (0.0, 2.0)
    assert bars == downbeats


def test_downbeats_3_4_meter() -> None:
    beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    downbeats, _bars = downbeats_from_beats(beats, beats_per_bar=3)
    assert downbeats == (0.0, 1.5, 3.0)


def test_downbeats_truncates_partial_bar() -> None:
    beats = [0.0, 0.5, 1.0, 1.5, 2.0]
    downbeats, bars = downbeats_from_beats(beats, beats_per_bar=4)
    assert downbeats == (0.0,)
    assert bars == (0.0,)


def test_downbeats_handles_invalid_beats_per_bar() -> None:
    beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
    downbeats, _bars = downbeats_from_beats(beats, beats_per_bar=0)
    # Invalid bpb falls back to 4.
    assert downbeats == (0.0, 2.0)


def test_downbeats_empty_input() -> None:
    downbeats, bars = downbeats_from_beats([], beats_per_bar=4)
    assert downbeats == ()
    assert bars == ()


# ── phase ────────────────────────────────────────────────────────────


def test_phase_returns_zero_for_empty_input() -> None:
    assert phase_from_first_beat([], 0.5) == 0.0


def test_phase_returns_zero_when_period_invalid() -> None:
    assert phase_from_first_beat([0.123], 0.0) == 0.0


def test_phase_is_within_beat_period() -> None:
    beats = [0.123]
    period = 0.5
    phase = phase_from_first_beat(beats, period)
    assert 0.0 <= phase < period
    assert phase == pytest.approx(0.123, abs=1e-9)


def test_phase_handles_negative_first_beat() -> None:
    phase = phase_from_first_beat([-0.3], 0.5)
    assert 0.0 <= phase < 0.5


# ── tempo curve ─────────────────────────────────────────────────────


def test_tempo_curve_empty_for_too_few_beats() -> None:
    assert tempo_curve_from_beat_times([], beats_per_bar=4) == ()
    assert tempo_curve_from_beat_times([0.0, 0.5], beats_per_bar=4) == ()


def test_tempo_curve_recovers_steady_bpm() -> None:
    """50 beats at 128 BPM → curve BPMs all close to 128."""
    ibi = 60.0 / 128.0
    beats = [0.0]
    for _ in range(50):
        beats.append(beats[-1] + ibi)
    curve = tempo_curve_from_beat_times(beats, beats_per_bar=4, window_bars=4)
    assert len(curve) >= 1
    for point in curve:
        assert abs(point.bpm - 128.0) < 0.5
        assert 0.0 <= point.confidence <= 1.0


def test_tempo_curve_window_size_affects_density() -> None:
    ibi = 60.0 / 130.0
    beats = [0.0]
    for _ in range(60):
        beats.append(beats[-1] + ibi)
    dense = tempo_curve_from_beat_times(beats, beats_per_bar=4, window_bars=2)
    sparse = tempo_curve_from_beat_times(beats, beats_per_bar=4, window_bars=8)
    assert len(dense) >= len(sparse)


# ── phrase boundaries ───────────────────────────────────────────────


def test_phrase_boundaries_too_few_bars() -> None:
    bars = [0.0, 0.5, 1.0]
    assert derive_phrase_boundaries(bars, min_phrase_bars=8) == ()


def test_phrase_boundaries_snap_to_8_bars() -> None:
    n = 16
    bars = [i * 2.0 for i in range(n)]
    boundaries = derive_phrase_boundaries(bars)
    assert boundaries[0] == 0.0
    assert boundaries[-1] == bars[-1]
    # 16 / 8 = 2 boundaries, plus a final close-out at bar 15.
    assert len(boundaries) == 3
    # Equal-spaced (plus final close-out)
    assert boundaries == (0.0, 16.0, 30.0)


def test_phrase_boundaries_24_bars() -> None:
    n = 24
    bars = [i * 2.0 for i in range(n)]
    boundaries = derive_phrase_boundaries(bars, min_phrase_bars=8)
    # 24 / 8 = 3 boundaries, plus final close-out.
    assert len(boundaries) == 4
    assert boundaries[0] == 0.0
    assert boundaries[-1] == bars[-1]


def test_phrase_boundaries_25_bars_falls_back() -> None:
    """25 bars is not divisible by 8/16/32 — falls back to min_phrase_bars."""
    n = 25
    bars = [i * 2.0 for i in range(n)]
    boundaries = derive_phrase_boundaries(bars, min_phrase_bars=8)
    # Step = 8, so boundaries at 0, 8, 16, 24 + close-out.
    assert boundaries[0] == 0.0
    assert boundaries[-1] == bars[-1]


# ── octave resolution ───────────────────────────────────────────────


def test_resolve_octave_returns_only_hypothesis() -> None:
    h = TempoHypothesis(bpm=128.0, confidence=0.5, octave_preference=1.0)
    out = resolve_octave([h])
    assert out is h


def test_resolve_octave_empty_returns_zero() -> None:
    out = resolve_octave([])
    assert out.bpm == 0.0
    assert out.confidence == 0.0


def test_resolve_octave_prefers_1x_when_no_hint() -> None:
    hyps = [
        TempoHypothesis(bpm=128.0, confidence=0.5, octave_preference=0.9),
        TempoHypothesis(bpm=64.0, confidence=0.5, octave_preference=0.1),
    ]
    out = resolve_octave(hyps)
    assert out.bpm == 128.0


def test_resolve_octave_uses_preferred_bpm() -> None:
    """When the caller says 'BPM is ~160', pick the 2x even if 1x dominates."""
    hyps = [
        TempoHypothesis(bpm=128.0, confidence=0.9, octave_preference=0.95),
        TempoHypothesis(bpm=256.0, confidence=0.8, octave_preference=0.05),
    ]
    out = resolve_octave(hyps, preferred_bpm=160.0)
    # 128 is closer to 160 (delta 32) than 256 is (delta 96).
    assert out.bpm == 128.0


def test_resolve_octave_picks_2x_when_preferred_near_double() -> None:
    hyps = [
        TempoHypothesis(bpm=128.0, confidence=0.9, octave_preference=0.95),
        TempoHypothesis(bpm=256.0, confidence=0.8, octave_preference=0.05),
    ]
    out = resolve_octave(hyps, preferred_bpm=255.0)
    assert out.bpm == 256.0


def test_resolve_octave_falls_back_to_highest_preference() -> None:
    """All candidates outside the 1x cluster → use octave_preference * conf."""
    hyps = [
        TempoHypothesis(bpm=80.0, confidence=0.5, octave_preference=0.1),
        TempoHypothesis(bpm=160.0, confidence=0.5, octave_preference=0.7),
    ]
    out = resolve_octave(hyps)
    assert out.bpm == 160.0


# ── is_multiple_of_bpm ──────────────────────────────────────────────


def test_is_multiple_of_bpm_true_for_doubles() -> None:
    assert is_multiple_of_bpm(256.0, 128.0)
    assert is_multiple_of_bpm(64.0, 128.0)


def test_is_multiple_of_bpm_false_for_unrelated() -> None:
    assert not is_multiple_of_bpm(130.0, 128.0)


def test_is_multiple_of_bpm_handles_zero() -> None:
    assert not is_multiple_of_bpm(0.0, 128.0)
    assert not is_multiple_of_bpm(128.0, 0.0)


# ── round_bpm ───────────────────────────────────────────────────────


def test_round_bpm_steps_to_cent_precision() -> None:
    assert round_bpm(128.4567) == 128.46


def test_round_bpm_handles_inf() -> None:
    assert round_bpm(float("inf")) == 0.0
    assert round_bpm(float("-inf")) == 0.0
    assert round_bpm(float("nan")) == 0.0


# ── BeatGrid roundtrip ──────────────────────────────────────────────


def test_beatgrid_beat_period_and_bar_period() -> None:
    grid = beatgrid_from_arrays(
        bpm=128.0,
        bpm_confidence=0.9,
        bpm_stability=0.95,
        variable_tempo=False,
        beats_per_bar=4,
        beat_times_s=(0.0, 0.46875, 0.9375, 1.40625, 1.875),
        downbeat_times_s=(0.0, 1.875),
        bar_times_s=(0.0, 1.875),
        phase_s=0.0,
    )
    assert grid.beat_period_s == pytest.approx(60.0 / 128.0)
    assert grid.bar_period_s == pytest.approx(60.0 / 128.0 * 4)
    assert grid.n_beats == 5
    assert grid.n_bars == 2


def test_beatgrid_to_dict_roundtrips_essentials() -> None:
    grid = beatgrid_from_arrays(
        bpm=128.0,
        bpm_confidence=0.9,
        bpm_stability=0.95,
        variable_tempo=False,
        beats_per_bar=4,
        beat_times_s=(0.0, 0.5, 1.0, 1.5),
        downbeat_times_s=(0.0,),
        bar_times_s=(0.0,),
        phase_s=0.0,
        hypotheses=(TempoHypothesis(bpm=128.0, confidence=0.9, octave_preference=1.0),),
        tempo_curve=(TempoCurvePoint(t_s=1.0, bpm=128.0, confidence=0.9),),
        phrase_boundaries_s=(0.0,),
    )
    d = grid.to_dict()
    assert d["bpm"] == 128.0
    assert d["beats_per_bar"] == 4
    assert d["beat_times_s"] == [0.0, 0.5, 1.0, 1.5]
    assert d["hypotheses"][0]["bpm"] == 128.0
    assert d["tempo_curve"][0]["bpm"] == 128.0
    assert d["phrase_boundaries_s"] == [0.0]


def test_beatgrid_first_beat_s() -> None:
    grid = beatgrid_from_arrays(
        bpm=128.0,
        bpm_confidence=0.9,
        bpm_stability=0.95,
        variable_tempo=False,
        beats_per_bar=4,
        beat_times_s=(0.123, 0.6, 1.1, 1.6),
        downbeat_times_s=(0.123,),
        bar_times_s=(0.123,),
        phase_s=0.123,
    )
    assert grid.first_beat_s() == pytest.approx(0.123)


def test_beatgrid_first_beat_s_empty() -> None:
    grid = beatgrid_from_arrays(
        bpm=0.0,
        bpm_confidence=0.0,
        bpm_stability=0.0,
        variable_tempo=False,
        beats_per_bar=4,
        beat_times_s=(),
        downbeat_times_s=(),
        bar_times_s=(),
        phase_s=0.0,
    )
    assert grid.first_beat_s() == 0.0


def test_beatgrid_clamps_invalid_beats_per_bar() -> None:
    grid = beatgrid_from_arrays(
        bpm=120.0,
        bpm_confidence=0.5,
        bpm_stability=0.5,
        variable_tempo=False,
        beats_per_bar=0,
        beat_times_s=(0.0, 0.5, 1.0, 1.5),
        downbeat_times_s=(0.0,),
        bar_times_s=(0.0,),
        phase_s=0.0,
    )
    assert grid.beats_per_bar == 4


def test_beatgrid_clamps_confidence_and_stability() -> None:
    grid = beatgrid_from_arrays(
        bpm=120.0,
        bpm_confidence=1.5,  # out of range
        bpm_stability=-0.2,  # out of range
        variable_tempo=True,
        beats_per_bar=4,
        beat_times_s=(0.0, 0.5),
        downbeat_times_s=(0.0,),
        bar_times_s=(0.0,),
        phase_s=0.0,
    )
    assert grid.bpm_confidence == 1.0
    assert grid.bpm_stability == 0.0
    assert grid.variable_tempo is True
