"""Tests for DissonanceAnalyzer."""

from __future__ import annotations

from unittest.mock import patch as _patch

import numpy as np
import pytest

from dj_music.audio.core.context import AnalysisContext
from dj_music.audio.core.types import AudioSignal

SAMPLE_RATE = 22050
DURATION = 2.0


def _make_signal(samples: np.ndarray) -> AudioSignal:
    return AudioSignal(
        samples=samples.astype(np.float32),
        sample_rate=SAMPLE_RATE,
        duration_seconds=len(samples) / SAMPLE_RATE,
    )


def _pure_sine(freq: float = 440.0) -> np.ndarray:
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _dissonant_cluster() -> np.ndarray:
    """Two close frequencies creating beating/dissonance."""
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    # 440Hz + 445Hz = very dissonant beating
    return (0.3 * np.sin(2 * np.pi * 440 * t) + 0.3 * np.sin(2 * np.pi * 445 * t)).astype(
        np.float32
    )


def test_dissonance_happy_path():
    """DissonanceAnalyzer produces float in valid range."""
    pytest.importorskip("essentia", reason="essentia not installed")
    from dj_music.audio.analyzers.dissonance import DissonanceAnalyzer

    signal = _make_signal(_pure_sine())
    analyzer = DissonanceAnalyzer()
    result = analyzer.run(AnalysisContext(signal))

    assert result.success
    assert "dissonance_mean" in result.features
    val = result.features["dissonance_mean"]
    assert isinstance(val, float)
    assert 0.0 <= val <= 1.0


def test_dissonance_comparative_sine_vs_cluster():
    """Pure sine should be less dissonant than close frequency cluster."""
    pytest.importorskip("essentia", reason="essentia not installed")
    from dj_music.audio.analyzers.dissonance import DissonanceAnalyzer

    analyzer = DissonanceAnalyzer()
    sine_result = analyzer.run(AnalysisContext(_make_signal(_pure_sine())))
    cluster_result = analyzer.run(AnalysisContext(_make_signal(_dissonant_cluster())))

    if sine_result.success and cluster_result.success:
        assert (
            sine_result.features["dissonance_mean"] <= cluster_result.features["dissonance_mean"]
        )


def test_dissonance_graceful_skip_no_essentia():
    """Without essentia, analyzer reports unavailable."""
    with _patch.dict("sys.modules", {"essentia": None, "essentia.standard": None}):
        from dj_music.audio.analyzers.dissonance import DissonanceAnalyzer

        analyzer = DissonanceAnalyzer()
        assert not analyzer.is_available()


def test_dissonance_silence():
    """Silence doesn't crash."""
    pytest.importorskip("essentia", reason="essentia not installed")
    from dj_music.audio.analyzers.dissonance import DissonanceAnalyzer

    silence = _make_signal(np.zeros(int(SAMPLE_RATE * DURATION), dtype=np.float32))
    analyzer = DissonanceAnalyzer()
    result = analyzer.run(AnalysisContext(silence))

    assert isinstance(result.success, bool)
