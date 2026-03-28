"""Spectral DSP primitives — extracted from spectral.py, energy.py, key.py.

Pure functions, zero side effects, zero app/ dependencies.
Eliminates duplicated FFT/windowing code across 3 analyzer files.
"""

from __future__ import annotations

import numpy as np


def compute_stft(
    samples: np.ndarray,
    frame_length: int = 2048,
    hop_length: int = 512,
    window: str = "hann",
) -> np.ndarray:
    """Compute Short-Time Fourier Transform.

    Returns complex STFT matrix of shape (n_fft_bins, n_frames)
    where n_fft_bins = frame_length // 2 + 1.
    """
    n_samples = len(samples)
    n_fft_bins = frame_length // 2 + 1
    n_frames = max(1, (n_samples - frame_length) // hop_length + 1)

    stft_matrix = np.zeros((n_fft_bins, n_frames), dtype=np.complex128)

    win = np.hanning(frame_length) if window == "hann" else np.ones(frame_length)

    for i in range(n_frames):
        start = i * hop_length
        end = min(start + frame_length, n_samples)
        frame = samples[start:end]

        if len(frame) < frame_length:
            frame = np.pad(frame, (0, frame_length - len(frame)))

        windowed = frame * win
        stft_matrix[:, i] = np.fft.rfft(windowed)

    return stft_matrix


def band_energies(
    magnitude: np.ndarray,
    freqs: np.ndarray,
    bands: dict[str, tuple[float, float]],
) -> dict[str, float]:
    """Compute relative energy in each frequency band.

    Args:
        magnitude: |STFT| matrix, shape (n_fft_bins, n_frames).
                   If 2D, uses mean across frames. If 1D, uses directly.
        freqs: FFT frequency bin centers, shape (n_fft_bins,).
        bands: Band name -> (low_hz, high_hz).

    Returns:
        Dict of band name -> relative energy (0-1, sums to ~1.0).
    """
    mag_mean = np.mean(magnitude, axis=1) if magnitude.ndim == 2 else magnitude

    power = mag_mean**2
    total_energy = float(np.sum(power))
    if total_energy == 0:
        return {name: 0.0 for name in bands}

    result: dict[str, float] = {}
    for name, (low_hz, high_hz) in bands.items():
        mask = (freqs >= low_hz) & (freqs < high_hz)
        band_energy = float(np.sum(power[mask]))
        result[name] = band_energy / total_energy

    return result


def spectral_centroid(magnitude: np.ndarray, freqs: np.ndarray) -> float:
    """Compute spectral centroid (weighted mean frequency).

    If 2D magnitude matrix, returns mean centroid across frames.
    """
    if magnitude.ndim == 2:
        centroids = []
        for i in range(magnitude.shape[1]):
            frame_mag = magnitude[:, i]
            total = float(np.sum(frame_mag))
            if total > 0:
                centroids.append(float(np.sum(freqs * frame_mag) / total))
            else:
                centroids.append(0.0)
        return float(np.mean(centroids)) if centroids else 0.0

    total = float(np.sum(magnitude))
    return float(np.sum(freqs * magnitude) / total) if total > 0 else 0.0


def spectral_rolloff(magnitude: np.ndarray, freqs: np.ndarray, pct: float = 0.85) -> float:
    """Compute spectral rolloff frequency.

    Returns frequency below which `pct` of total spectral energy lies.
    If 2D magnitude, returns mean rolloff across frames.
    """
    if magnitude.ndim == 2:
        rolloffs = []
        for i in range(magnitude.shape[1]):
            frame_mag = magnitude[:, i]
            total = float(np.sum(frame_mag))
            if total > 0:
                cumsum = np.cumsum(frame_mag)
                idx = np.searchsorted(cumsum, pct * total)
                idx = min(idx, len(freqs) - 1)
                rolloffs.append(float(freqs[idx]))
            else:
                rolloffs.append(0.0)
        return float(np.mean(rolloffs)) if rolloffs else 0.0

    total = float(np.sum(magnitude))
    if total <= 0:
        return 0.0
    cumsum = np.cumsum(magnitude)
    idx = np.searchsorted(cumsum, pct * total)
    idx = min(idx, len(freqs) - 1)
    return float(freqs[idx])


def spectral_flatness(magnitude: np.ndarray) -> float:
    """Compute spectral flatness (geometric mean / arithmetic mean).

    Returns value in [0, 1]. 1.0 = white noise, 0.0 = pure tone.
    If 2D magnitude, returns mean flatness across frames.
    """
    if magnitude.ndim == 2:
        flatness_values = []
        for i in range(magnitude.shape[1]):
            flatness_values.append(_flatness_1d(magnitude[:, i]))
        return float(np.mean(flatness_values)) if flatness_values else 0.0

    return _flatness_1d(magnitude)


def _flatness_1d(mag: np.ndarray) -> float:
    """Flatness for a single frame."""
    positive = mag[mag > 0]
    if len(positive) == 0:
        return 0.0
    log_mean = float(np.mean(np.log(positive + 1e-10)))
    geometric_mean = np.exp(log_mean)
    arithmetic_mean = float(np.mean(mag))
    if arithmetic_mean <= 0:
        return 0.0
    return float(geometric_mean / (arithmetic_mean + 1e-10))
