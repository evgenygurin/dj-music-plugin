"""Tests for core analyzers (loudness, energy, spectral).

Uses synthetic audio signals with known properties:
- 440Hz sine wave: known spectral centroid
- White noise: flatness near 1.0
- Silence: baseline reference
"""

from __future__ import annotations

import numpy as np

from app.audio.analyzers.energy import EnergyAnalyzer
from app.audio.analyzers.loudness import LoudnessAnalyzer
from app.audio.analyzers.spectral import SpectralAnalyzer
from app.audio.core.context import AnalysisContext
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


def _run(analyzer: object, signal: AudioSignal) -> object:  # type: ignore[type-arg]
    """Run analyzer synchronously via new API."""
    from app.audio.analyzers.base import BaseAnalyzer

    assert isinstance(analyzer, BaseAnalyzer)
    return analyzer.run(AnalysisContext(signal))


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


class TestLoudnessAnalyzer:
    def test_rms_is_negative_for_quiet(self) -> None:
        analyzer = LoudnessAnalyzer()
        signal = _make_signal(_quiet_signal())
        result = _run(analyzer, signal)
        assert result.success is True
        assert result.features["rms_dbfs"] < -30.0

    def test_louder_has_higher_rms(self) -> None:
        analyzer = LoudnessAnalyzer()
        quiet = _run(analyzer, _make_signal(_sine_wave(amplitude=0.1)))
        loud = _run(analyzer, _make_signal(_sine_wave(amplitude=0.8)))
        assert loud.features["rms_dbfs"] > quiet.features["rms_dbfs"]

    def test_true_peak_gte_rms(self) -> None:
        analyzer = LoudnessAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        assert result.features["true_peak_db"] >= result.features["rms_dbfs"]

    def test_crest_factor_positive(self) -> None:
        analyzer = LoudnessAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        assert result.features["crest_factor_db"] >= 0.0

    def test_lufs_less_than_zero(self) -> None:
        analyzer = LoudnessAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave(amplitude=0.5)))
        assert result.features["integrated_lufs"] < 0.0

    def test_loudness_range_nonnegative(self) -> None:
        analyzer = LoudnessAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        assert result.features["loudness_range_lu"] >= 0.0

    def test_empty_signal_fails(self) -> None:
        analyzer = LoudnessAnalyzer()
        signal = _make_signal(np.array([], dtype=np.float32))
        result = _run(analyzer, signal)
        assert result.success is False

    def test_all_features_present(self) -> None:
        analyzer = LoudnessAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        expected = {
            "integrated_lufs",
            "short_term_lufs_mean",
            "momentary_max",
            "rms_dbfs",
            "true_peak_db",
            "crest_factor_db",
            "loudness_range_lu",
        }
        assert set(result.features.keys()) == expected

    def test_short_term_lufs_mean_reasonable(self) -> None:
        """Short-term LUFS mean should be close to integrated LUFS for steady signal."""
        analyzer = LoudnessAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        integrated = result.features["integrated_lufs"]
        short_term = result.features["short_term_lufs_mean"]
        # For a steady sine wave, short-term mean ≈ integrated (within 2 dB)
        assert abs(short_term - integrated) < 2.0

    def test_momentary_max_gte_integrated(self) -> None:
        """Momentary max should be >= integrated LUFS."""
        analyzer = LoudnessAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        assert result.features["momentary_max"] >= result.features["integrated_lufs"] - 0.1

    def test_momentary_max_higher_for_dynamic_signal(self) -> None:
        """A signal with loud bursts should have higher momentary max than steady signal."""
        analyzer = LoudnessAnalyzer()
        # Create a signal with loud burst at the start
        steady = _sine_wave(amplitude=0.2)
        burst = _sine_wave(amplitude=0.9)
        dynamic = np.copy(steady)
        burst_len = min(len(burst), int(SAMPLE_RATE * 0.5))
        dynamic[:burst_len] = burst[:burst_len]

        steady_result = _run(analyzer, _make_signal(steady))
        dynamic_result = _run(analyzer, _make_signal(dynamic))
        assert dynamic_result.features["momentary_max"] > steady_result.features["momentary_max"]

    def test_short_signal_fallback(self) -> None:
        """Signal shorter than 3s should still produce short_term and momentary values."""
        analyzer = LoudnessAnalyzer()
        # 0.5 second signal
        short_samples = _sine_wave()[: int(SAMPLE_RATE * 0.5)]
        result = _run(analyzer, _make_signal(short_samples))
        assert result.success is True
        assert "short_term_lufs_mean" in result.features
        assert "momentary_max" in result.features


# ── Energy Analyzer ──────────────────────────────────────────────────


class TestEnergyAnalyzer:
    def test_energy_mean_between_0_and_1(self) -> None:
        analyzer = EnergyAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        assert 0.0 <= result.features["energy_mean"] <= 1.0

    def test_energy_max_between_0_and_1(self) -> None:
        analyzer = EnergyAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        assert 0.0 <= result.features["energy_max"] <= 1.0

    def test_energy_std_nonnegative(self) -> None:
        analyzer = EnergyAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        assert result.features["energy_std"] >= 0.0

    def test_six_bands_present(self) -> None:
        analyzer = EnergyAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        band_keys = [
            k
            for k in result.features
            if k.startswith("energy_")
            and not k.endswith("_ratio")
            and k not in ("energy_mean", "energy_max", "energy_std", "energy_slope")
        ]
        assert len(band_keys) == 6

    def test_bands_sum_approximately_to_total(self) -> None:
        """Band energies should sum close to 1.0 (they're relative to total FFT energy)."""
        analyzer = EnergyAnalyzer()
        # Use white noise for broader frequency coverage
        result = _run(analyzer, _make_signal(_white_noise()))
        band_names = (
            "energy_sub",
            "energy_low",
            "energy_lowmid",
            "energy_mid",
            "energy_highmid",
            "energy_high",
        )
        band_sum = sum(result.features.get(k, 0.0) for k in band_names)
        # Allow some tolerance — very high/low frequencies may be outside bands
        assert 0.5 < band_sum <= 1.01

    def test_sine_energy_concentrated_in_one_band(self) -> None:
        """440Hz should concentrate energy in the lowmid band (250-500 Hz)."""
        analyzer = EnergyAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave(freq=440.0)))
        assert result.features["energy_lowmid"] > 0.5

    def test_click_track_has_higher_std(self) -> None:
        """Click track should have higher energy variability than sine wave."""
        analyzer = EnergyAnalyzer()
        sine_result = _run(analyzer, _make_signal(_sine_wave()))
        click_result = _run(analyzer, _make_signal(_click_track()))
        assert click_result.features["energy_std"] > sine_result.features["energy_std"]

    def test_empty_signal_fails(self) -> None:
        analyzer = EnergyAnalyzer()
        signal = _make_signal(np.array([], dtype=np.float32))
        result = _run(analyzer, signal)
        assert result.success is False


# ── Spectral Analyzer ────────────────────────────────────────────────


class TestSpectralAnalyzer:
    def test_centroid_for_sine_near_440(self) -> None:
        """Spectral centroid of 440Hz sine should be near 440Hz."""
        analyzer = SpectralAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave(freq=440.0)))
        centroid = result.features["spectral_centroid_hz"]
        # Allow generous tolerance for windowed FFT
        assert 400.0 < centroid < 500.0

    def test_higher_freq_has_higher_centroid(self) -> None:
        analyzer = SpectralAnalyzer()
        low = _run(analyzer, _make_signal(_sine_wave(freq=200.0)))
        high = _run(analyzer, _make_signal(_sine_wave(freq=4000.0)))
        assert high.features["spectral_centroid_hz"] > low.features["spectral_centroid_hz"]

    def test_flatness_for_noise_near_one(self) -> None:
        """White noise should have spectral flatness closer to 1.0."""
        analyzer = SpectralAnalyzer()
        result = _run(analyzer, _make_signal(_white_noise()))
        flatness = result.features["spectral_flatness"]
        # White noise flatness is typically 0.5-1.0 depending on windowing
        assert flatness > 0.3

    def test_flatness_for_sine_near_zero(self) -> None:
        """Pure sine wave should have very low spectral flatness."""
        analyzer = SpectralAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        flatness = result.features["spectral_flatness"]
        assert flatness < 0.1

    def test_rolloff_95_gte_85(self) -> None:
        analyzer = SpectralAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        assert result.features["spectral_rolloff_95"] >= result.features["spectral_rolloff_85"]

    def test_flux_nonnegative(self) -> None:
        analyzer = SpectralAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        assert result.features["spectral_flux_mean"] >= 0.0
        assert result.features["spectral_flux_std"] >= 0.0

    def test_all_features_present(self) -> None:
        analyzer = SpectralAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
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

    def test_spectral_slope_is_finite(self) -> None:
        """Spectral slope should be a finite number."""
        analyzer = SpectralAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        slope = result.features["spectral_slope"]
        assert np.isfinite(slope)

    def test_spectral_slope_negative_for_sine(self) -> None:
        """Sine wave concentrates energy at one frequency, so slope should be negative
        (magnitude drops off from that peak across the spectrum)."""
        analyzer = SpectralAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        # Sine wave has a very steep slope (energy concentrated at fundamental)
        assert result.features["spectral_slope"] < 0.0

    def test_spectral_contrast_positive_for_sine(self) -> None:
        """Sine wave should have high contrast (peak at fundamental vs noise floor)."""
        analyzer = SpectralAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        assert result.features["spectral_contrast"] > 0.0

    def test_spectral_contrast_lower_for_noise(self) -> None:
        """White noise should have lower contrast than sine (more uniform spectrum)."""
        analyzer = SpectralAnalyzer()
        sine_result = _run(analyzer, _make_signal(_sine_wave()))
        noise_result = _run(analyzer, _make_signal(_white_noise()))
        assert (
            noise_result.features["spectral_contrast"] < sine_result.features["spectral_contrast"]
        )

    def test_empty_signal_fails(self) -> None:
        analyzer = SpectralAnalyzer()
        signal = _make_signal(np.array([], dtype=np.float32))
        result = _run(analyzer, signal)
        assert result.success is False
