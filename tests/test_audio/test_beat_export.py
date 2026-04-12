"""Tests for BeatDetector beat_times export."""

from __future__ import annotations

import numpy as np
import pytest

from dj_music.audio.analyzers.beat import BeatDetector
from dj_music.audio.core.context import AnalysisContext
from dj_music.audio.core.types import AudioSignal

SAMPLE_RATE = 22050


def _make_kick_signal(bpm: float = 130.0, duration: float = 4.0) -> AudioSignal:
    """Generate a synthetic kick pattern at given BPM."""
    n_samples = int(SAMPLE_RATE * duration)
    samples = np.zeros(n_samples, dtype=np.float32)
    beat_interval = 60.0 / bpm
    t = 0.0
    while t < duration:
        idx = int(t * SAMPLE_RATE)
        # Short impulse (10ms kick)
        end_idx = min(idx + int(0.01 * SAMPLE_RATE), n_samples)
        kick_len = end_idx - idx
        if kick_len > 0:
            samples[idx:end_idx] = 0.8 * np.sin(
                2 * np.pi * 60 * np.arange(kick_len) / SAMPLE_RATE
            ).astype(np.float32)
        t += beat_interval
    return AudioSignal(samples=samples, sample_rate=SAMPLE_RATE, duration_seconds=duration)


def test_beat_detector_exports_beat_times():
    """BeatDetector output must include beat_times as list of floats."""
    pytest.importorskip("librosa")
    signal = _make_kick_signal(bpm=130.0, duration=4.0)
    detector = BeatDetector()
    result = detector.run(AnalysisContext(signal))

    assert result.success
    assert "beat_times" in result.features, "beat_times missing from BeatDetector output"
    bt = result.features["beat_times"]
    assert isinstance(bt, list)
    assert len(bt) > 0
    assert all(isinstance(t, float) for t in bt)


def test_beat_export_includes_intervals():
    """BeatDetector must export beats_intervals with length == len(beat_times) - 1."""
    pytest.importorskip("librosa")
    signal = _make_kick_signal(bpm=130.0, duration=4.0)
    detector = BeatDetector()
    result = detector.run(AnalysisContext(signal))

    assert result.success
    assert "beats_intervals" in result.features, "beats_intervals missing from BeatDetector output"

    bt = result.features["beat_times"]
    bi = result.features["beats_intervals"]

    assert isinstance(bi, list)
    assert len(bi) == len(bt) - 1, f"Expected {len(bt) - 1} intervals, got {len(bi)}"
    assert all(isinstance(v, float) and v > 0 for v in bi), "All intervals must be positive floats"


# ── Sanity checks for the optimized HPSS-via-decompose path ────────────


def test_kick_pattern_has_high_kick_prominence_and_low_hp_ratio():
    """A pure kick pattern should be percussive-dominated.

    kick_prominence: percussive low-band fraction → near 1.0 for a 60Hz kick
    hp_ratio: harmonic/percussive RMS → low for percussion-only signal
    """
    pytest.importorskip("librosa")
    signal = _make_kick_signal(bpm=130.0, duration=8.0)
    result = BeatDetector().run(AnalysisContext(signal))
    assert result.success

    feats = result.features
    # 60Hz kick with 200Hz cutoff → most percussive energy is in the
    # low band, so kick_prominence should dominate.
    assert feats["kick_prominence"] > 0.5, (
        f"kick_prominence={feats['kick_prominence']} too low for pure kick pattern"
    )
    assert 0.0 <= feats["kick_prominence"] <= 1.0
    assert feats["hp_ratio"] >= 0.0


def test_pure_sine_has_high_hp_ratio_and_low_kick_prominence():
    """A pure tone is harmonic, not percussive — opposite of kick pattern.

    hp_ratio: high (no percussion to divide by, but the lower bound of
    the divisor is the eps so result stays finite).
    kick_prominence: low (a 440 Hz sine has nothing below 200 Hz).
    """
    pytest.importorskip("librosa")
    duration = 6.0
    n = int(SAMPLE_RATE * duration)
    samples = (0.4 * np.sin(2 * np.pi * 440 * np.arange(n) / SAMPLE_RATE)).astype(np.float32)
    signal = AudioSignal(samples=samples, sample_rate=SAMPLE_RATE, duration_seconds=duration)
    result = BeatDetector().run(AnalysisContext(signal))
    assert result.success

    feats = result.features
    # 440 Hz is well above the 200 Hz low-band → near zero kick prominence
    assert feats["kick_prominence"] < 0.1, (
        f"kick_prominence={feats['kick_prominence']} too high for 440Hz sine"
    )
    # Pure sine is dominantly harmonic
    assert feats["hp_ratio"] > 1.0, f"hp_ratio={feats['hp_ratio']} too low for harmonic signal"


def test_pulse_clarity_higher_for_periodic_than_noise():
    """Periodic kick pattern should have stronger pulse_clarity than noise."""
    pytest.importorskip("librosa")
    rng = np.random.default_rng(42)
    duration = 6.0
    n = int(SAMPLE_RATE * duration)

    noise = (0.1 * rng.standard_normal(n)).astype(np.float32)
    noise_sig = AudioSignal(samples=noise, sample_rate=SAMPLE_RATE, duration_seconds=duration)
    noise_result = BeatDetector().run(AnalysisContext(noise_sig))

    kick_sig = _make_kick_signal(bpm=130.0, duration=duration)
    kick_result = BeatDetector().run(AnalysisContext(kick_sig))

    assert noise_result.success and kick_result.success
    assert kick_result.features["pulse_clarity"] > noise_result.features["pulse_clarity"], (
        f"kick {kick_result.features['pulse_clarity']} not > noise "
        f"{noise_result.features['pulse_clarity']}"
    )
    assert 0.0 <= noise_result.features["pulse_clarity"] <= 1.0
    assert 0.0 <= kick_result.features["pulse_clarity"] <= 1.0
