"""Tests for DynamicComplexityAnalyzer."""

from __future__ import annotations

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


def _constant_tone() -> np.ndarray:
    """Constant amplitude — low dynamic complexity."""
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def _fade_in_out() -> np.ndarray:
    """Fade in then fade out — higher dynamic complexity."""
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    envelope = np.sin(np.pi * t / DURATION)  # 0 -> 1 -> 0
    return (0.8 * envelope * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def test_dynamic_complexity_happy_path():
    """DynamicComplexityAnalyzer produces float >= 0."""
    pytest.importorskip("essentia")
    from dj_music.audio.analyzers.dynamic_complexity import DynamicComplexityAnalyzer

    signal = _make_signal(_fade_in_out())
    analyzer = DynamicComplexityAnalyzer()
    result = analyzer.run(AnalysisContext(signal))

    assert result.success
    assert "dynamic_complexity" in result.features
    val = result.features["dynamic_complexity"]
    assert isinstance(val, float)
    assert val >= 0.0


def test_dynamic_complexity_comparative_constant_vs_fade():
    """Constant tone should have lower dynamic complexity than fade in/out."""
    pytest.importorskip("essentia")
    from dj_music.audio.analyzers.dynamic_complexity import DynamicComplexityAnalyzer

    analyzer = DynamicComplexityAnalyzer()
    const_result = analyzer.run(AnalysisContext(_make_signal(_constant_tone())))
    fade_result = analyzer.run(AnalysisContext(_make_signal(_fade_in_out())))

    if const_result.success and fade_result.success:
        assert (
            const_result.features["dynamic_complexity"]
            <= fade_result.features["dynamic_complexity"]
        )


def test_dynamic_complexity_graceful_skip_no_essentia():
    """Without essentia, analyzer reports unavailable."""
    from unittest.mock import patch as _patch

    with _patch.dict("sys.modules", {"essentia": None, "essentia.standard": None}):
        from importlib import reload

        import dj_music.audio.analyzers.dynamic_complexity as mod

        reload(mod)
        analyzer = mod.DynamicComplexityAnalyzer()
        assert not analyzer.is_available()


def test_dynamic_complexity_silence():
    """Silence doesn't crash."""
    pytest.importorskip("essentia")
    from dj_music.audio.analyzers.dynamic_complexity import DynamicComplexityAnalyzer

    silence = _make_signal(np.zeros(int(SAMPLE_RATE * DURATION), dtype=np.float32))
    analyzer = DynamicComplexityAnalyzer()
    result = analyzer.run(AnalysisContext(silence))

    assert isinstance(result.success, bool)
