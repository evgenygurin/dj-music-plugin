"""Tests for SpectralComplexityAnalyzer."""

from __future__ import annotations

import numpy as np
import pytest

from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

SAMPLE_RATE = 22050
DURATION = 3.0


def _make_signal(samples: np.ndarray) -> AudioSignal:
    return AudioSignal(
        samples=samples.astype(np.float32),
        sample_rate=SAMPLE_RATE,
        duration_seconds=len(samples) / SAMPLE_RATE,
    )


def _pure_sine(freq: float = 440.0) -> np.ndarray:
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _noise_burst() -> np.ndarray:
    rng = np.random.default_rng(42)
    return (0.3 * rng.standard_normal(int(SAMPLE_RATE * DURATION))).astype(np.float32)


def test_spectral_complexity_happy_path():
    pytest.importorskip("essentia", reason="essentia not installed")
    from app.audio.analyzers.spectral_complexity import SpectralComplexityAnalyzer

    signal = _make_signal(_pure_sine())
    analyzer = SpectralComplexityAnalyzer()
    result = analyzer.run(AnalysisContext(signal))

    assert result.success
    assert "spectral_complexity_mean" in result.features
    val = result.features["spectral_complexity_mean"]
    assert isinstance(val, float)
    assert val >= 0.0


def test_spectral_complexity_noise_higher_than_sine():
    pytest.importorskip("essentia", reason="essentia not installed")
    from app.audio.analyzers.spectral_complexity import SpectralComplexityAnalyzer

    analyzer = SpectralComplexityAnalyzer()
    sine_result = analyzer.run(AnalysisContext(_make_signal(_pure_sine())))
    noise_result = analyzer.run(AnalysisContext(_make_signal(_noise_burst())))

    if sine_result.success and noise_result.success:
        assert (
            noise_result.features["spectral_complexity_mean"]
            > sine_result.features["spectral_complexity_mean"]
        )


def test_spectral_complexity_graceful_skip_no_essentia():
    from unittest.mock import patch

    with patch.dict("sys.modules", {"essentia": None, "essentia.standard": None}):
        from app.audio.analyzers.spectral_complexity import SpectralComplexityAnalyzer

        analyzer = SpectralComplexityAnalyzer()
        assert not analyzer.is_available()
