"""Tests for BeatsLoudnessAnalyzer (dependent on BeatDetector)."""

from __future__ import annotations

import numpy as np
import pytest

from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

SAMPLE_RATE = 22050
DURATION = 4.0


def _make_signal(samples: np.ndarray) -> AudioSignal:
    return AudioSignal(
        samples=samples.astype(np.float32),
        sample_rate=SAMPLE_RATE,
        duration_seconds=len(samples) / SAMPLE_RATE,
    )


def _kick_pattern(bpm: float = 130.0) -> np.ndarray:
    n = int(SAMPLE_RATE * DURATION)
    samples = np.zeros(n, dtype=np.float32)
    interval = int(60.0 / bpm * SAMPLE_RATE)
    for start in range(0, n, interval):
        end = min(start + int(0.01 * SAMPLE_RATE), n)
        kick_len = end - start
        if kick_len > 0:
            samples[start:end] = 0.8 * np.sin(
                2 * np.pi * 60 * np.arange(kick_len) / SAMPLE_RATE
            ).astype(np.float32)
    return samples


def _beat_times_for_bpm(bpm: float = 130.0) -> list[float]:
    """Generate synthetic beat times."""
    interval = 60.0 / bpm
    times: list[float] = []
    t = 0.0
    while t < DURATION:
        times.append(t)
        t += interval
    return times


def test_beats_loudness_happy_path():
    """With beat_times, produces 6D band ratio vector."""
    pytest.importorskip("essentia")
    from app.audio.analyzers.beats_loudness import BeatsLoudnessAnalyzer

    signal = _make_signal(_kick_pattern())
    analyzer = BeatsLoudnessAnalyzer()
    assert analyzer.depends_on == frozenset({"beat"})

    prior = {"beat_times": _beat_times_for_bpm(130.0)}
    result = analyzer.run(AnalysisContext(signal), prior)

    assert result.success
    assert "beat_loudness_band_ratio" in result.features
    vec = result.features["beat_loudness_band_ratio"]
    assert isinstance(vec, list)
    assert len(vec) == 6, f"Expected 6 bands, got {len(vec)}"
    assert all(isinstance(v, float) for v in vec)


def test_beats_loudness_no_beat_times():
    """Without beat_times in prior_results, returns empty dict (graceful)."""
    pytest.importorskip("essentia")
    from app.audio.analyzers.beats_loudness import BeatsLoudnessAnalyzer

    signal = _make_signal(_kick_pattern())
    analyzer = BeatsLoudnessAnalyzer()

    # No prior_results
    result = analyzer.run(AnalysisContext(signal), None)
    assert result.success
    assert result.features == {}

    # prior_results without beat_times
    result2 = analyzer.run(AnalysisContext(signal), {"other_key": 42})
    assert result2.success
    assert result2.features == {}


def test_beats_loudness_empty_beat_times():
    """Empty beat_times list returns empty dict."""
    pytest.importorskip("essentia")
    from app.audio.analyzers.beats_loudness import BeatsLoudnessAnalyzer

    signal = _make_signal(_kick_pattern())
    analyzer = BeatsLoudnessAnalyzer()

    result = analyzer.run(AnalysisContext(signal), {"beat_times": []})
    assert result.success
    assert result.features == {}


def test_beats_loudness_graceful_skip_no_essentia():
    """Without essentia, analyzer reports unavailable."""
    from unittest.mock import patch as _patch

    with _patch.dict("sys.modules", {"essentia": None, "essentia.standard": None}):
        from importlib import reload

        import app.audio.analyzers.beats_loudness as mod

        reload(mod)
        analyzer = mod.BeatsLoudnessAnalyzer()
        assert not analyzer.is_available()


def test_beats_loudness_silence():
    """Silence with beat_times doesn't crash."""
    pytest.importorskip("essentia")
    from app.audio.analyzers.beats_loudness import BeatsLoudnessAnalyzer

    silence = _make_signal(np.zeros(int(SAMPLE_RATE * DURATION), dtype=np.float32))
    analyzer = BeatsLoudnessAnalyzer()

    result = analyzer.run(AnalysisContext(silence), {"beat_times": [0.5, 1.0, 1.5]})
    assert isinstance(result.success, bool)
