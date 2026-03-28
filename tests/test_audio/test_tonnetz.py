"""Tests for TonnetzAnalyzer."""

from __future__ import annotations

import numpy as np
import pytest

from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

SAMPLE_RATE = 22050
DURATION = 2.0


def _make_signal(samples: np.ndarray) -> AudioSignal:
    return AudioSignal(
        samples=samples.astype(np.float32),
        sample_rate=SAMPLE_RATE,
        duration_seconds=len(samples) / SAMPLE_RATE,
    )


def _pure_a4() -> np.ndarray:
    """Pure A4 (440Hz) — known pitch for deterministic tonal features."""
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def test_tonnetz_happy_path():
    """TonnetzAnalyzer produces 6D vector of floats."""
    pytest.importorskip("librosa")
    from app.audio.analyzers.tonnetz import TonnetzAnalyzer

    signal = _make_signal(_pure_a4())
    analyzer = TonnetzAnalyzer()
    result = analyzer.run(AnalysisContext(signal))

    assert result.success
    assert "tonnetz_vector" in result.features
    vec = result.features["tonnetz_vector"]
    assert isinstance(vec, list)
    assert len(vec) == 6, f"Expected 6D tonnetz, got {len(vec)}D"
    assert all(isinstance(v, float) for v in vec)


def test_tonnetz_values_in_range():
    """Tonnetz values should be in [-1.5, 1.5] range."""
    pytest.importorskip("librosa")
    from app.audio.analyzers.tonnetz import TonnetzAnalyzer

    signal = _make_signal(_pure_a4())
    analyzer = TonnetzAnalyzer()
    result = analyzer.run(AnalysisContext(signal))

    if result.success:
        for val in result.features["tonnetz_vector"]:
            assert -1.5 <= val <= 1.5, f"Tonnetz value {val} out of expected range"


def test_tonnetz_graceful_skip_no_librosa():
    """Without librosa, analyzer reports unavailable."""
    from unittest.mock import patch as _patch

    with _patch.dict("sys.modules", {"librosa": None, "librosa.feature": None}):
        from importlib import reload

        import app.audio.analyzers.tonnetz as mod

        reload(mod)
        analyzer = mod.TonnetzAnalyzer()
        assert not analyzer.is_available()


def test_tonnetz_silence():
    """Silence doesn't crash."""
    pytest.importorskip("librosa")
    from app.audio.analyzers.tonnetz import TonnetzAnalyzer

    silence = _make_signal(np.zeros(int(SAMPLE_RATE * DURATION), dtype=np.float32))
    analyzer = TonnetzAnalyzer()
    result = analyzer.run(AnalysisContext(silence))

    assert isinstance(result.success, bool)
