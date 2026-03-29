"""Tests for SpectralAnalyzer — vectorized implementation using ctx.magnitude.

Regression tests to verify the vectorized rewrite produces correct results
and all 8 output keys are present with valid ranges.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.audio.analyzers.spectral import SpectralAnalyzer
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


def _sine(freq: float) -> np.ndarray:
    """Generate pure sine wave."""
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), dtype=np.float32)
    return 0.5 * np.sin(2 * np.pi * freq * t)


@pytest.fixture
def analyzer() -> SpectralAnalyzer:
    return SpectralAnalyzer()


class TestSpectralOutputKeys:
    """All 8 expected keys must be present and finite."""

    def test_all_keys_present(self, analyzer: SpectralAnalyzer) -> None:
        signal = _make_signal(_sine(440.0))
        ctx = AnalysisContext(signal)
        result = analyzer.run(ctx)
        assert result.success
        expected = {
            "spectral_centroid_hz",
            "spectral_rolloff_85",
            "spectral_rolloff_95",
            "spectral_flatness",
            "spectral_flux_mean",
            "spectral_flux_std",
            "spectral_slope",
            "spectral_contrast",
        }
        assert set(result.features.keys()) == expected

    def test_all_values_finite(self, analyzer: SpectralAnalyzer) -> None:
        signal = _make_signal(_sine(440.0))
        ctx = AnalysisContext(signal)
        result = analyzer.run(ctx)
        for key, val in result.features.items():
            assert np.isfinite(val), f"{key} = {val} is not finite"


class TestSpectralCentroid:
    """Centroid should reflect dominant frequency."""

    def test_sine_440_centroid_near_440(self, analyzer: SpectralAnalyzer) -> None:
        signal = _make_signal(_sine(440.0))
        ctx = AnalysisContext(signal)
        result = analyzer.run(ctx)
        centroid = result.features["spectral_centroid_hz"]
        # Pure sine: centroid should be near 440 Hz (within windowing effects)
        assert 400.0 < centroid < 500.0, f"centroid={centroid} not near 440"

    def test_high_freq_higher_centroid(self, analyzer: SpectralAnalyzer) -> None:
        lo = _make_signal(_sine(200.0))
        hi = _make_signal(_sine(4000.0))
        ctx_lo = AnalysisContext(lo)
        ctx_hi = AnalysisContext(hi)
        c_lo = analyzer.run(ctx_lo).features["spectral_centroid_hz"]
        c_hi = analyzer.run(ctx_hi).features["spectral_centroid_hz"]
        assert c_hi > c_lo


class TestSpectralFlatness:
    """Flatness: 0 = tonal (pure sine), ~1 = noise."""

    def test_sine_low_flatness(self, analyzer: SpectralAnalyzer) -> None:
        signal = _make_signal(_sine(440.0))
        ctx = AnalysisContext(signal)
        flatness = analyzer.run(ctx).features["spectral_flatness"]
        # Pure sine should have low flatness (< 0.1)
        assert flatness < 0.15, f"flatness={flatness} too high for sine"

    def test_noise_higher_flatness(self, analyzer: SpectralAnalyzer) -> None:
        rng = np.random.default_rng(42)
        noise = rng.standard_normal(int(SAMPLE_RATE * DURATION)).astype(np.float32) * 0.3
        signal = _make_signal(noise)
        ctx = AnalysisContext(signal)
        flatness = analyzer.run(ctx).features["spectral_flatness"]
        assert flatness > 0.5, f"flatness={flatness} too low for noise"


class TestSpectralFlux:
    """Flux: change between consecutive frames."""

    def test_steady_sine_low_flux(self, analyzer: SpectralAnalyzer) -> None:
        signal = _make_signal(_sine(440.0))
        ctx = AnalysisContext(signal)
        flux = analyzer.run(ctx).features["spectral_flux_mean"]
        assert flux < 0.05, f"flux={flux} too high for steady sine"


class TestEmptySignal:
    """Empty signal should not crash."""

    def test_empty_signal_fails_gracefully(self, analyzer: SpectralAnalyzer) -> None:
        signal = _make_signal(np.zeros(0, dtype=np.float32))
        ctx = AnalysisContext(signal)
        result = analyzer.run(ctx)
        assert not result.success  # Empty signal guard in BaseAnalyzer
