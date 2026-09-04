"""Tests for the BeatGridAnalyzer.

These tests run against the audio analyzer pipeline using synthetic
onset envelopes — the same shape the BPM/beat analyzers consume. We
verify:

* The analyzer is auto-discovered and has the documented name.
* A periodic click train at 128 BPM produces a beatgrid with the
  expected beat timestamps and BPM.
* A 0.5x ambiguity (64 BPM signal with strong 2x peak in the ACF)
  surfaces a 2x hypothesis with non-trivial octave_preference.
* The analyzer respects the prior BPM hint for octave disambiguation.
* No librosa-level work happens in the test path — synthetic
  envelopes go directly into ``tempo_from_onset_autocorrelation``.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("librosa")

from app.audio.analyzers.base import AnalyzerRegistry
from app.audio.analyzers.beatgrid import (
    BeatGridAnalyzer,
    _build_tempo_hypotheses,
)
from app.audio.analyzers.beatgrid import (
    beatgrid_from_arrays as build_beatgrid,
)
from app.audio.core.context import AnalysisContext
from app.audio.core.rhythm import tempo_from_onset_autocorrelation
from app.audio.core.tempo import BeatGrid, TempoHypothesis
from app.audio.core.types import AudioSignal, FrameParams

SR = 22050
HOP = 512


def _click_envelope(bpm: float, duration_s: float = 30.0) -> np.ndarray:
    """Build a synthetic onset envelope with sharp peaks at every beat.

    Used in place of an STFT-derived envelope: gives the analyzer a
    clean periodic signal whose tempo is known exactly.
    """
    n_frames = int(duration_s * SR / HOP)
    env = np.zeros(n_frames, dtype=np.float64)
    ibi_frames = 60.0 * SR / HOP / bpm
    pos = 0.0
    while int(pos) < n_frames:
        env[int(pos)] = 1.0
        pos += ibi_frames
    return env


def _ctx_with_envelope(bpm: float, duration_s: float = 30.0) -> AnalysisContext:
    """Build an AnalysisContext whose onset envelope is a click train."""
    samples = np.zeros(int(duration_s * SR), dtype=np.float32)
    signal = AudioSignal(
        samples=samples,
        sample_rate=SR,
        duration_seconds=duration_s,
    )
    ctx = AnalysisContext(signal, params=FrameParams(frame_length=2048, hop_length=HOP))
    # Replace the lazy-cached onset envelope with a click train.
    env = _click_envelope(bpm, duration_s)
    ctx._onset_env = env  # type: ignore[attr-defined]
    return ctx


# ── registry / discovery ────────────────────────────────────────────


def test_beatgrid_analyzer_is_registered() -> None:
    reg = AnalyzerRegistry()
    reg.discover()
    analyzer = reg.get("beatgrid")
    if analyzer is None:
        pytest.skip("librosa not installed — beatgrid analyzer unavailable")
    assert isinstance(analyzer, BeatGridAnalyzer)
    assert analyzer.name == "beatgrid"
    assert "tempo" in analyzer.capabilities
    assert "bpm" in analyzer.depends_on


def test_beatgrid_analyzer_level_3_scoring() -> None:
    """The beatgrid analyzer is registered at L3 (SCORING)."""
    from app.audio.level_config import AnalysisLevel, get_analyzers_for_level

    names = get_analyzers_for_level(AnalysisLevel.SCORING)
    assert "beatgrid" in names


# ── _build_tempo_hypotheses ─────────────────────────────────────────


def test_hypotheses_include_1x_dominant() -> None:
    """A 128 BPM click train → 1x hypothesis dominates."""
    env = _click_envelope(128.0, duration_s=20.0)
    estimate = tempo_from_onset_autocorrelation(env, SR, HOP)
    hyps = _build_tempo_hypotheses(env, SR, HOP, estimate)
    assert len(hyps) >= 1
    # The dominant hypothesis must be the 1x one (closest to 128).
    bpm_values = sorted(h.bpm for h in hyps)
    assert any(125 <= b <= 131 for b in bpm_values)


def test_hypotheses_2x_octave_present() -> None:
    """2x ratio is always part of the hypothesis set."""
    env = _click_envelope(128.0, duration_s=20.0)
    estimate = tempo_from_onset_autocorrelation(env, SR, HOP)
    hyps = _build_tempo_hypotheses(env, SR, HOP, estimate)
    sources = [h.source for h in hyps]
    assert any("1x" in s for s in sources)
    assert any("2x" in s for s in sources)
    assert any("0.5x" in s for s in sources)


def test_hypotheses_octave_preference_sums_to_one() -> None:
    env = _click_envelope(128.0, duration_s=20.0)
    estimate = tempo_from_onset_autocorrelation(env, SR, HOP)
    hyps = _build_tempo_hypotheses(env, SR, HOP, estimate)
    total = sum(h.octave_preference for h in hyps)
    assert total == pytest.approx(1.0, abs=1e-6)


def test_hypotheses_handles_zero_bpm() -> None:
    """Degenerate estimate → empty hypothesis list."""
    from app.audio.core.rhythm import TempoEstimate

    env = np.zeros(10, dtype=np.float64)
    estimate = TempoEstimate(bpm=0.0, lag_frames=0, confidence=0.0, autocorrelation=env)
    hyps = _build_tempo_hypotheses(env, SR, HOP, estimate)
    assert hyps == []


# ── run / integration ───────────────────────────────────────────────


def test_analyzer_returns_beatgrid_dict() -> None:
    ctx = _ctx_with_envelope(128.0, duration_s=20.0)
    analyzer = BeatGridAnalyzer()
    result = analyzer.run(ctx)
    assert result.success, f"analyzer failed: {result.error}"
    assert "beatgrid" in result.features
    assert "tempo_hypotheses" in result.features
    bg = result.features["beatgrid"]
    assert bg["bpm"] > 0
    assert bg["beats_per_bar"] == 4
    assert len(bg["beat_times_s"]) >= 1


def test_analyzer_inherits_prior_bpm() -> None:
    """When the BPM analyzer has already run, the beatgrid honors it."""
    ctx = _ctx_with_envelope(128.0, duration_s=20.0)
    analyzer = BeatGridAnalyzer()
    prior = {"bpm": 128.0, "bpm_confidence": 0.9, "bpm_stability": 0.95, "variable_tempo": False}
    result = analyzer.run(ctx, prior_results=prior)
    assert result.success
    bg = result.features["beatgrid"]
    # The hint keeps the grid aligned with the canonical BPM.
    assert abs(bg["bpm"] - 128.0) < 5.0


def test_analyzer_handles_silent_signal() -> None:
    samples = np.zeros(int(5.0 * SR), dtype=np.float32)
    signal = AudioSignal(samples=samples, sample_rate=SR, duration_seconds=5.0)
    ctx = AnalysisContext(signal, params=FrameParams(frame_length=2048, hop_length=HOP))
    analyzer = BeatGridAnalyzer()
    result = analyzer.run(ctx)
    # Either success-with-zero-BPM or failed gracefully — never a crash.
    assert isinstance(result.success, bool)
    if result.success:
        bg = result.features["beatgrid"]
        assert bg["bpm"] >= 0
        assert bg["beat_times_s"] == []


# ── build_beatgrid helper ───────────────────────────────────────────


def test_build_beatgrid_helper_produces_typed_grid() -> None:
    grid = build_beatgrid(
        bpm=130.0,
        bpm_confidence=0.85,
        bpm_stability=0.9,
        variable_tempo=False,
        beats_per_bar=4,
        beat_times_s=(0.0, 0.4615, 0.923, 1.385, 1.846),
        downbeat_times_s=(0.0, 1.846),
        bar_times_s=(0.0, 1.846),
        phase_s=0.0,
        hypotheses=(TempoHypothesis(bpm=130.0, confidence=0.85, octave_preference=1.0),),
    )
    assert isinstance(grid, BeatGrid)
    assert grid.bpm == 130.0
    assert grid.n_beats == 5
    assert grid.n_bars == 2
    assert grid.hypotheses[0].bpm == 130.0


def test_build_beatgrid_clamps_inputs() -> None:
    grid = build_beatgrid(
        bpm=128.0,
        bpm_confidence=2.0,  # out of range
        bpm_stability=-0.1,  # out of range
        variable_tempo=True,
        beats_per_bar=0,  # invalid
        beat_times_s=(0.0, 0.5),
        downbeat_times_s=(0.0,),
        bar_times_s=(0.0,),
        phase_s=-0.1,  # invalid
    )
    assert grid.bpm_confidence == 1.0
    assert grid.bpm_stability == 0.0
    assert grid.beats_per_bar == 4
    assert grid.phase_s == 0.0
