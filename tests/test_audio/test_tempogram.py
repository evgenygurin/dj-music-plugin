"""Tests for TempogramAnalyzer."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from dj_music.audio.core.context import AnalysisContext
from dj_music.audio.core.types import AudioSignal

SAMPLE_RATE = 22050
DURATION = 4.0


def _make_signal(samples: np.ndarray) -> AudioSignal:
    return AudioSignal(
        samples=samples.astype(np.float32),
        sample_rate=SAMPLE_RATE,
        duration_seconds=len(samples) / SAMPLE_RATE,
    )


def _click_track(bpm: float = 130.0) -> np.ndarray:
    """Generate click track at given BPM."""
    n = int(SAMPLE_RATE * DURATION)
    samples = np.zeros(n, dtype=np.float32)
    interval = int(60.0 / bpm * SAMPLE_RATE)
    for start in range(0, n, interval):
        end = min(start + 5, n)  # very short click
        samples[start:end] = 0.9
    return samples


def test_tempogram_happy_path():
    """TempogramAnalyzer produces vector of floats."""
    pytest.importorskip("librosa")
    from dj_music.audio.analyzers.tempogram import TempogramAnalyzer

    signal = _make_signal(_click_track())
    analyzer = TempogramAnalyzer()
    result = analyzer.run(AnalysisContext(signal))

    assert result.success
    assert "tempogram_ratio_vector" in result.features
    vec = result.features["tempogram_ratio_vector"]
    assert isinstance(vec, list)
    assert len(vec) > 0
    assert all(isinstance(v, float) for v in vec)
    assert all(0.0 <= v <= 1.0 for v in vec)


def test_tempogram_graceful_skip_no_librosa():
    """Without librosa, analyzer reports unavailable."""
    with patch.dict("sys.modules", {"librosa": None}):
        from dj_music.audio.analyzers.tempogram import TempogramAnalyzer

        analyzer = TempogramAnalyzer()
        assert not analyzer.is_available()


def test_tempogram_short_audio():
    """Very short audio (<1s) doesn't crash."""
    from dj_music.audio.analyzers.tempogram import TempogramAnalyzer

    short = _make_signal(
        np.random.default_rng(42).standard_normal(int(SAMPLE_RATE * 0.5)).astype(np.float32)
    )
    analyzer = TempogramAnalyzer()
    result = analyzer.run(AnalysisContext(short))

    # Either success or graceful error — no crash
    assert isinstance(result.success, bool)
