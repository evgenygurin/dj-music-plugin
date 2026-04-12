"""Tests for DanceabilityAnalyzer."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from dj_music.audio.core.context import AnalysisContext
from dj_music.audio.core.types import AudioSignal

SAMPLE_RATE = 22050
DURATION = 3.0


def _make_signal(samples: np.ndarray) -> AudioSignal:
    return AudioSignal(
        samples=samples.astype(np.float32),
        sample_rate=SAMPLE_RATE,
        duration_seconds=len(samples) / SAMPLE_RATE,
    )


def _kick_pattern(bpm: float = 130.0) -> np.ndarray:
    """Generate rhythmic kick pattern — should score higher danceability."""
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


def test_danceability_happy_path():
    """DanceabilityAnalyzer produces float in valid range."""
    pytest.importorskip("essentia", reason="essentia not installed")
    from dj_music.audio.analyzers.danceability import DanceabilityAnalyzer

    signal = _make_signal(_kick_pattern())
    analyzer = DanceabilityAnalyzer()
    result = analyzer.run(AnalysisContext(signal))

    assert result.success
    assert "danceability" in result.features
    val = result.features["danceability"]
    assert isinstance(val, float)
    assert val >= 0.0


def test_danceability_graceful_skip_no_essentia():
    """Without essentia, analyzer reports unavailable."""
    with patch.dict("sys.modules", {"essentia": None, "essentia.standard": None}):
        from dj_music.audio.analyzers.danceability import DanceabilityAnalyzer

        analyzer = DanceabilityAnalyzer()
        assert not analyzer.is_available()


def test_danceability_silence():
    """Silence produces a valid (likely low) danceability value, no crash."""
    from dj_music.audio.analyzers.danceability import DanceabilityAnalyzer

    silence = _make_signal(np.zeros(int(SAMPLE_RATE * DURATION), dtype=np.float32))
    analyzer = DanceabilityAnalyzer()
    result = analyzer.run(AnalysisContext(silence))

    # Either success with low value, or graceful failure — no crash
    if result.success:
        assert result.features["danceability"] >= 0.0
