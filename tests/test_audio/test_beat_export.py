"""Tests for BeatDetector: metrically regular beats and downbeat detection."""

from __future__ import annotations

import numpy as np
import pytest

from app.audio.analyzers.beat import BeatDetector, _find_downbeat_phase, _safe_normalize
from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

SAMPLE_RATE = 22050


def _make_kick_signal(bpm: float = 130.0, duration: float = 8.0) -> AudioSignal:
    """Generate a synthetic kick pattern at given BPM."""
    n_samples = int(SAMPLE_RATE * duration)
    samples = np.zeros(n_samples, dtype=np.float32)
    beat_interval = 60.0 / bpm
    t = 0.0
    while t < duration:
        idx = int(t * SAMPLE_RATE)
        end_idx = min(idx + int(0.01 * SAMPLE_RATE), n_samples)
        kick_len = end_idx - idx
        if kick_len > 0:
            samples[idx:end_idx] = 0.8 * np.sin(
                2 * np.pi * 60 * np.arange(kick_len) / SAMPLE_RATE
            ).astype(np.float32)
        t += beat_interval
    return AudioSignal(samples=samples, sample_rate=SAMPLE_RATE, duration_seconds=duration)


def _make_downbeat_signal(
    bpm: float = 128.0, duration: float = 16.0, downbeat_phase: int = 0
) -> AudioSignal:
    """Generate a signal with accented downbeats for testing."""
    n_samples = int(SAMPLE_RATE * duration)
    samples = np.zeros(n_samples, dtype=np.float32)
    beat_interval = 60.0 / bpm
    t = 0.0
    beat_idx = 0
    while t < duration:
        idx = int(t * SAMPLE_RATE)
        end_idx = min(idx + int(0.02 * SAMPLE_RATE), n_samples)
        kick_len = end_idx - idx
        if kick_len > 0:
            time_arr = np.arange(kick_len) / SAMPLE_RATE
            kick = 0.6 * np.sin(2 * np.pi * 60 * time_arr)
            if (beat_idx - downbeat_phase) % 4 == 0:
                kick = 0.9 * np.sin(2 * np.pi * 60 * time_arr)
                bass = 0.5 * np.sin(2 * np.pi * 200 * time_arr)
                kick += bass
            samples[idx:end_idx] += kick.astype(np.float32)
        t += beat_interval
        beat_idx += 1
    return AudioSignal(samples=samples, sample_rate=SAMPLE_RATE, duration_seconds=duration)


# ── Original tests (from main) ──────────────────────────────────


def test_beat_detector_exports_beat_times():
    pytest.importorskip("librosa")
    signal = _make_kick_signal(bpm=130.0, duration=8.0)
    result = BeatDetector().run(AnalysisContext(signal))
    assert result.success
    bt = result.features["beat_times"]
    assert isinstance(bt, list) and len(bt) > 0
    assert all(isinstance(t, float) for t in bt)


def test_beat_export_includes_intervals():
    pytest.importorskip("librosa")
    signal = _make_kick_signal(bpm=130.0, duration=8.0)
    result = BeatDetector().run(AnalysisContext(signal))
    assert result.success
    bt = result.features["beat_times"]
    bi = result.features["beats_intervals"]
    assert len(bi) == len(bt) - 1
    assert all(isinstance(v, float) and v > 0 for v in bi)


def test_kick_pattern_has_high_kick_prominence_and_low_hp_ratio():
    pytest.importorskip("librosa")
    signal = _make_kick_signal(bpm=130.0, duration=8.0)
    result = BeatDetector().run(AnalysisContext(signal))
    assert result.success
    assert result.features["kick_prominence"] > 0.5
    assert 0.0 <= result.features["kick_prominence"] <= 1.0
    assert result.features["hp_ratio"] >= 0.0


def test_pure_sine_has_high_hp_ratio_and_low_kick_prominence():
    pytest.importorskip("librosa")
    n = int(SAMPLE_RATE * 6.0)
    samples = (0.4 * np.sin(2 * np.pi * 440 * np.arange(n) / SAMPLE_RATE)).astype(np.float32)
    signal = AudioSignal(samples=samples, sample_rate=SAMPLE_RATE, duration_seconds=6.0)
    result = BeatDetector().run(AnalysisContext(signal))
    assert result.success
    assert result.features["kick_prominence"] < 0.1
    assert result.features["hp_ratio"] > 1.0


def test_pulse_clarity_higher_for_periodic_than_noise():
    pytest.importorskip("librosa")
    rng = np.random.default_rng(42)
    n = int(SAMPLE_RATE * 6.0)
    noise_sig = AudioSignal(
        samples=(0.1 * rng.standard_normal(n)).astype(np.float32),
        sample_rate=SAMPLE_RATE,
        duration_seconds=6.0,
    )
    kick_sig = _make_kick_signal(bpm=130.0, duration=6.0)
    nr = BeatDetector().run(AnalysisContext(noise_sig))
    kr = BeatDetector().run(AnalysisContext(kick_sig))
    assert nr.success and kr.success
    assert kr.features["pulse_clarity"] > nr.features["pulse_clarity"]


# ── Downbeat detection tests ─────────────────────────────


def test_beat_times_are_metrically_regular():
    pytest.importorskip("librosa")
    signal = _make_kick_signal(bpm=130.0, duration=8.0)
    result = BeatDetector().run(AnalysisContext(signal))
    assert result.success
    bi = result.features["beats_intervals"]
    if len(bi) >= 4:
        cv = float(np.std(bi) / np.mean(bi)) if np.mean(bi) > 0 else 1.0
        assert cv < 0.15, f"Beat intervals too irregular (CV={cv:.3f})"


def test_downbeat_fields_present():
    pytest.importorskip("librosa")
    signal = _make_kick_signal(bpm=130.0, duration=8.0)
    result = BeatDetector().run(AnalysisContext(signal))
    assert result.success
    f = result.features
    assert "downbeat_times" in f
    assert "first_downbeat_ms" in f
    assert "downbeat_confidence" in f
    assert isinstance(f["downbeat_times"], list)
    assert isinstance(f["first_downbeat_ms"], float)
    assert 0.0 <= f["downbeat_confidence"] <= 1.0


def test_downbeat_times_are_subset_of_beat_times():
    pytest.importorskip("librosa")
    signal = _make_kick_signal(bpm=128.0, duration=16.0)
    result = BeatDetector().run(AnalysisContext(signal))
    assert result.success
    bt_set = set(result.features["beat_times"])
    for dt in result.features["downbeat_times"]:
        assert dt in bt_set


def test_downbeat_times_are_every_4th_beat():
    pytest.importorskip("librosa")
    signal = _make_kick_signal(bpm=128.0, duration=16.0)
    result = BeatDetector().run(AnalysisContext(signal))
    assert result.success
    bt = result.features["beat_times"]
    dt = result.features["downbeat_times"]
    if len(dt) >= 2 and len(bt) >= 8:
        first_db_idx = bt.index(dt[0])
        for i, db_time in enumerate(dt):
            expected_idx = first_db_idx + i * 4
            if expected_idx < len(bt):
                assert bt[expected_idx] == db_time


def test_downbeat_detection_with_accented_downbeats():
    pytest.importorskip("librosa")
    signal = _make_downbeat_signal(bpm=128.0, duration=16.0, downbeat_phase=0)
    result = BeatDetector().run(AnalysisContext(signal))
    assert result.success
    assert len(result.features["downbeat_times"]) >= 2
    assert result.features["downbeat_confidence"] >= 0.0


def test_safe_normalize():
    arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    normed = _safe_normalize(arr)
    assert abs(normed.min()) < 1e-10
    assert abs(normed.max() - 1.0) < 1e-10
    assert np.all(_safe_normalize(np.array([3.0, 3.0, 3.0])) == 0.0)


def test_find_downbeat_phase_too_few_beats():
    pytest.importorskip("librosa")
    import librosa

    signal = _make_kick_signal(bpm=130.0, duration=4.0)
    ctx = AnalysisContext(signal)
    beat_times = [0.5, 1.0, 1.5, 2.0]
    beat_frames = librosa.time_to_frames(beat_times, sr=signal.sample_rate)
    phase, conf = _find_downbeat_phase(
        beat_times=beat_times,
        beat_frames=beat_frames,
        samples=signal.samples,
        sr=signal.sample_rate,
        magnitude=ctx.magnitude,
        freqs=ctx.freqs,
    )
    assert phase == 0
    assert conf == 0.0


def test_traditional_features_preserved():
    pytest.importorskip("librosa")
    signal = _make_kick_signal(bpm=130.0, duration=8.0)
    result = BeatDetector().run(AnalysisContext(signal))
    assert result.success
    f = result.features
    assert isinstance(f["onset_rate"], float) and f["onset_rate"] > 0.0
    assert isinstance(f["pulse_clarity"], float) and 0.0 <= f["pulse_clarity"] <= 1.0
    assert isinstance(f["kick_prominence"], float) and 0.0 <= f["kick_prominence"] <= 1.0
    assert isinstance(f["hp_ratio"], float)
