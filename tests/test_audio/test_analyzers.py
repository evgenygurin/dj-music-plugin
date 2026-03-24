"""Tests for core analyzers (loudness, energy, spectral).

Uses synthetic audio signals with known properties:
- 440Hz sine wave: known spectral centroid
- White noise: flatness near 1.0
- Silence: baseline reference
"""

from __future__ import annotations

import numpy as np
import pytest

from app.audio.analyzers.energy import EnergyAnalyzer
from app.audio.analyzers.loudness import LoudnessAnalyzer
from app.audio.analyzers.spectral import SpectralAnalyzer
from app.audio.registry import AudioSignal

SAMPLE_RATE = 22050
DURATION = 2.0  # seconds


def _make_signal(samples: np.ndarray) -> AudioSignal:
    """Helper to create AudioSignal from numpy array."""
    return AudioSignal(
        samples=samples.astype(np.float32),
        sample_rate=SAMPLE_RATE,
        duration_seconds=len(samples) / SAMPLE_RATE,
    )


def _sine_wave(freq: float = 440.0, amplitude: float = 0.5) -> np.ndarray:
    """Generate a pure sine wave."""
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _white_noise(amplitude: float = 0.3) -> np.ndarray:
    """Generate white noise."""
    rng = np.random.default_rng(42)
    n_samples = int(SAMPLE_RATE * DURATION)
    return (amplitude * rng.standard_normal(n_samples)).astype(np.float32)


def _click_track(interval_samples: int = 4410, amplitude: float = 0.8) -> np.ndarray:
    """Generate a simple click track (impulses at regular intervals)."""
    n_samples = int(SAMPLE_RATE * DURATION)
    samples = np.zeros(n_samples, dtype=np.float32)
    for i in range(0, n_samples, interval_samples):
        # Short burst (10 samples)
        end = min(i + 10, n_samples)
        samples[i:end] = amplitude
    return samples


def _quiet_signal() -> np.ndarray:
    """Very quiet sine wave."""
    return _sine_wave(freq=440.0, amplitude=0.01)


# ── Loudness Analyzer ────────────────────────────────────────────────


@pytest.mark.asyncio
class TestLoudnessAnalyzer:
    async def test_rms_is_negative_for_quiet(self) -> None:
        analyzer = LoudnessAnalyzer()
        signal = _make_signal(_quiet_signal())
        result = await analyzer.analyze(signal)
        assert result.success is True
        assert result.features["rms_dbfs"] < -30.0

    async def test_louder_has_higher_rms(self) -> None:
        analyzer = LoudnessAnalyzer()
        quiet = await analyzer.analyze(_make_signal(_sine_wave(amplitude=0.1)))
        loud = await analyzer.analyze(_make_signal(_sine_wave(amplitude=0.8)))
        assert loud.features["rms_dbfs"] > quiet.features["rms_dbfs"]

    async def test_true_peak_gte_rms(self) -> None:
        analyzer = LoudnessAnalyzer()
        result = await analyzer.analyze(_make_signal(_sine_wave()))
        assert result.features["true_peak_db"] >= result.features["rms_dbfs"]

    async def test_crest_factor_positive(self) -> None:
        analyzer = LoudnessAnalyzer()
        result = await analyzer.analyze(_make_signal(_sine_wave()))
        assert result.features["crest_factor_db"] >= 0.0

    async def test_lufs_less_than_zero(self) -> None:
        analyzer = LoudnessAnalyzer()
        result = await analyzer.analyze(_make_signal(_sine_wave(amplitude=0.5)))
        assert result.features["integrated_lufs"] < 0.0

    async def test_loudness_range_nonnegative(self) -> None:
        analyzer = LoudnessAnalyzer()
        result = await analyzer.analyze(_make_signal(_sine_wave()))
        assert result.features["loudness_range_lu"] >= 0.0

    async def test_empty_signal_fails(self) -> None:
        analyzer = LoudnessAnalyzer()
        signal = _make_signal(np.array([], dtype=np.float32))
        result = await analyzer.analyze(signal)
        assert result.success is False

    async def test_all_features_present(self) -> None:
        analyzer = LoudnessAnalyzer()
        result = await analyzer.analyze(_make_signal(_sine_wave()))
        expected = {
            "integrated_lufs",
            "rms_dbfs",
            "true_peak_db",
            "crest_factor_db",
            "loudness_range_lu",
        }
        assert set(result.features.keys()) == expected


# ── Energy Analyzer ──────────────────────────────────────────────────


@pytest.mark.asyncio
class TestEnergyAnalyzer:
    async def test_energy_mean_between_0_and_1(self) -> None:
        analyzer = EnergyAnalyzer()
        result = await analyzer.analyze(_make_signal(_sine_wave()))
        assert 0.0 <= result.features["energy_mean"] <= 1.0

    async def test_energy_max_between_0_and_1(self) -> None:
        analyzer = EnergyAnalyzer()
        result = await analyzer.analyze(_make_signal(_sine_wave()))
        assert 0.0 <= result.features["energy_max"] <= 1.0

    async def test_energy_std_nonnegative(self) -> None:
        analyzer = EnergyAnalyzer()
        result = await analyzer.analyze(_make_signal(_sine_wave()))
        assert result.features["energy_std"] >= 0.0

    async def test_seven_bands_present(self) -> None:
        analyzer = EnergyAnalyzer()
        result = await analyzer.analyze(_make_signal(_sine_wave()))
        band_keys = [k for k in result.features if k.startswith("energy_band_")]
        assert len(band_keys) == 7

    async def test_bands_sum_approximately_to_total(self) -> None:
        """Band energies should sum close to 1.0 (they're relative to total FFT energy)."""
        analyzer = EnergyAnalyzer()
        # Use white noise for broader frequency coverage
        result = await analyzer.analyze(_make_signal(_white_noise()))
        band_sum = sum(v for k, v in result.features.items() if k.startswith("energy_band_"))
        # Allow some tolerance — very high/low frequencies may be outside bands
        assert 0.5 < band_sum <= 1.01

    async def test_sine_energy_concentrated_in_one_band(self) -> None:
        """440Hz should concentrate energy in the low_mid band (250-500 Hz)."""
        analyzer = EnergyAnalyzer()
        result = await analyzer.analyze(_make_signal(_sine_wave(freq=440.0)))
        assert result.features["energy_band_low_mid"] > 0.5

    async def test_click_track_has_higher_std(self) -> None:
        """Click track should have higher energy variability than sine wave."""
        analyzer = EnergyAnalyzer()
        sine_result = await analyzer.analyze(_make_signal(_sine_wave()))
        click_result = await analyzer.analyze(_make_signal(_click_track()))
        assert click_result.features["energy_std"] > sine_result.features["energy_std"]

    async def test_empty_signal_fails(self) -> None:
        analyzer = EnergyAnalyzer()
        signal = _make_signal(np.array([], dtype=np.float32))
        result = await analyzer.analyze(signal)
        assert result.success is False


# ── Spectral Analyzer ────────────────────────────────────────────────


@pytest.mark.asyncio
class TestSpectralAnalyzer:
    async def test_centroid_for_sine_near_440(self) -> None:
        """Spectral centroid of 440Hz sine should be near 440Hz."""
        analyzer = SpectralAnalyzer()
        result = await analyzer.analyze(_make_signal(_sine_wave(freq=440.0)))
        centroid = result.features["spectral_centroid_hz"]
        # Allow generous tolerance for windowed FFT
        assert 400.0 < centroid < 500.0

    async def test_higher_freq_has_higher_centroid(self) -> None:
        analyzer = SpectralAnalyzer()
        low = await analyzer.analyze(_make_signal(_sine_wave(freq=200.0)))
        high = await analyzer.analyze(_make_signal(_sine_wave(freq=4000.0)))
        assert high.features["spectral_centroid_hz"] > low.features["spectral_centroid_hz"]

    async def test_flatness_for_noise_near_one(self) -> None:
        """White noise should have spectral flatness closer to 1.0."""
        analyzer = SpectralAnalyzer()
        result = await analyzer.analyze(_make_signal(_white_noise()))
        flatness = result.features["spectral_flatness"]
        # White noise flatness is typically 0.5-1.0 depending on windowing
        assert flatness > 0.3

    async def test_flatness_for_sine_near_zero(self) -> None:
        """Pure sine wave should have very low spectral flatness."""
        analyzer = SpectralAnalyzer()
        result = await analyzer.analyze(_make_signal(_sine_wave()))
        flatness = result.features["spectral_flatness"]
        assert flatness < 0.1

    async def test_rolloff_95_gte_85(self) -> None:
        analyzer = SpectralAnalyzer()
        result = await analyzer.analyze(_make_signal(_sine_wave()))
        assert result.features["spectral_rolloff_95"] >= result.features["spectral_rolloff_85"]

    async def test_flux_nonnegative(self) -> None:
        analyzer = SpectralAnalyzer()
        result = await analyzer.analyze(_make_signal(_sine_wave()))
        assert result.features["spectral_flux_mean"] >= 0.0
        assert result.features["spectral_flux_std"] >= 0.0

    async def test_all_features_present(self) -> None:
        analyzer = SpectralAnalyzer()
        result = await analyzer.analyze(_make_signal(_sine_wave()))
        expected = {
            "spectral_centroid_hz",
            "spectral_rolloff_85",
            "spectral_rolloff_95",
            "spectral_flatness",
            "spectral_flux_mean",
            "spectral_flux_std",
        }
        assert set(result.features.keys()) == expected

    async def test_empty_signal_fails(self) -> None:
        analyzer = SpectralAnalyzer()
        signal = _make_signal(np.array([], dtype=np.float32))
        result = await analyzer.analyze(signal)
        assert result.success is False
