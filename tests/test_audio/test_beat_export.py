"""Tests for BeatDetector beat_times export."""

from __future__ import annotations

import numpy as np
import pytest

from app.audio.analyzers.beat import BeatDetector
from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

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
