"""Tests for core spectral primitives."""

from __future__ import annotations

import numpy as np

from app.audio.core.spectral import (
    band_energies,
    compute_stft,
    spectral_centroid,
    spectral_flatness,
    spectral_rolloff,
)

SAMPLE_RATE = 22050


def _sine_samples(freq: float = 440.0, duration: float = 1.0) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


class TestComputeStft:
    def test_output_shape(self) -> None:
        samples = _sine_samples()
        stft = compute_stft(samples, frame_length=2048, hop_length=512)
        assert stft.shape[0] == 1025
        expected_frames = max(1, (len(samples) - 2048) // 512 + 1)
        assert stft.shape[1] == expected_frames

    def test_complex_output(self) -> None:
        stft = compute_stft(_sine_samples(), 2048, 512)
        assert np.iscomplexobj(stft)


class TestBandEnergies:
    def test_sine_440_in_lowmid(self) -> None:
        stft = compute_stft(_sine_samples(440.0), 2048, 512)
        magnitude = np.abs(stft)
        freqs = np.fft.rfftfreq(2048, d=1.0 / SAMPLE_RATE)
        bands = {"sub": (20, 60), "low": (60, 250), "lowmid": (250, 500), "mid": (500, 2000)}
        result = band_energies(magnitude, freqs, bands)
        assert result["lowmid"] > result["sub"]
        assert result["lowmid"] > result["mid"]

    def test_returns_all_bands(self) -> None:
        stft = compute_stft(_sine_samples(), 2048, 512)
        magnitude = np.abs(stft)
        freqs = np.fft.rfftfreq(2048, d=1.0 / SAMPLE_RATE)
        bands = {"low": (60, 250), "mid": (250, 2000), "high": (2000, 8000)}
        result = band_energies(magnitude, freqs, bands)
        assert set(result.keys()) == {"low", "mid", "high"}


class TestSpectralCentroid:
    def test_sine_centroid_near_freq(self) -> None:
        stft = compute_stft(_sine_samples(440.0), 2048, 512)
        magnitude = np.abs(stft)
        freqs = np.fft.rfftfreq(2048, d=1.0 / SAMPLE_RATE)
        centroid = spectral_centroid(magnitude, freqs)
        assert 400.0 < centroid < 500.0


class TestSpectralRolloff:
    def test_rolloff_95_gte_85(self) -> None:
        stft = compute_stft(_sine_samples(), 2048, 512)
        magnitude = np.abs(stft)
        freqs = np.fft.rfftfreq(2048, d=1.0 / SAMPLE_RATE)
        r85 = spectral_rolloff(magnitude, freqs, 0.85)
        r95 = spectral_rolloff(magnitude, freqs, 0.95)
        assert r95 >= r85


class TestSpectralFlatness:
    def test_sine_low_flatness(self) -> None:
        stft = compute_stft(_sine_samples(), 2048, 512)
        magnitude = np.abs(stft)
        flat = spectral_flatness(magnitude)
        assert flat < 0.1

    def test_noise_higher_flatness(self) -> None:
        rng = np.random.default_rng(42)
        noise = (0.3 * rng.standard_normal(22050)).astype(np.float32)
        stft = compute_stft(noise, 2048, 512)
        magnitude = np.abs(stft)
        flat = spectral_flatness(magnitude)
        assert flat > 0.3
