"""Rhythm helpers used by onset/beat/tempo analyzers.

These functions intentionally avoid librosa's numba-accelerated paths.
They operate on precomputed STFT magnitudes from ``AnalysisContext`` and
keep the analyzers deterministic and crash-free under Python 3.12.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class TempoEstimate:
    """Dominant tempo estimate derived from onset autocorrelation."""

    bpm: float
    lag_frames: float
    confidence: float
    autocorrelation: np.ndarray


def spectral_flux_onset_envelope(
    magnitude: np.ndarray,
    frame_energies: np.ndarray | None = None,
) -> np.ndarray:
    """Compute a normalized onset envelope from STFT magnitude."""
    if magnitude.size == 0:
        return np.zeros(1, dtype=np.float64)

    log_mag = np.log1p(np.asarray(magnitude, dtype=np.float64))
    flux = np.diff(log_mag, axis=1, prepend=log_mag[:, :1])
    flux = np.maximum(flux, 0.0)
    onset_env = np.sum(flux, axis=0)

    if frame_energies is not None and len(frame_energies) == len(onset_env):
        energies = np.asarray(frame_energies, dtype=np.float64)
        energy_delta = np.maximum(np.diff(energies, prepend=energies[:1]), 0.0)
        onset_env = onset_env + energy_delta

    if len(onset_env) >= 3:
        onset_env = np.convolve(
            onset_env,
            np.array([0.25, 0.5, 0.25], dtype=np.float64),
            mode="same",
        )

    max_value = float(np.max(onset_env))
    if max_value <= 0:
        return np.zeros_like(onset_env)
    return onset_env / max_value


def onset_autocorrelation(onset_env: np.ndarray) -> np.ndarray:
    """FFT-based autocorrelation of an onset envelope."""
    if len(onset_env) == 0:
        return np.zeros(1, dtype=np.float64)

    centered = np.asarray(onset_env, dtype=np.float64) - float(np.mean(onset_env))
    if not np.any(centered):
        return np.zeros(len(onset_env), dtype=np.float64)

    n = len(centered)
    nfft = 1 << (2 * n - 1).bit_length()
    spectrum = np.fft.rfft(centered, nfft)
    autocorr = np.fft.irfft(spectrum * np.conj(spectrum), nfft)[:n]
    return autocorr.astype(np.float64, copy=False)


def tempo_from_onset_autocorrelation(
    onset_env: np.ndarray,
    sr: int,
    hop_length: int,
    *,
    min_bpm: float = 110.0,
    max_bpm: float = 200.0,
) -> TempoEstimate:
    """Estimate tempo from onset-envelope autocorrelation."""
    if len(onset_env) < 4:
        return TempoEstimate(0.0, 0.0, 0.0, np.zeros(len(onset_env), dtype=np.float64))

    autocorr = onset_autocorrelation(onset_env)
    if len(autocorr) < 4 or float(autocorr[0]) <= 0:
        return TempoEstimate(0.0, 0.0, 0.0, autocorr)

    frames_per_sec = sr / hop_length
    min_lag = max(1, int(np.floor(60.0 * frames_per_sec / max_bpm)))
    max_lag = min(len(autocorr) - 2, int(np.ceil(60.0 * frames_per_sec / min_bpm)))
    if max_lag <= min_lag + 1:
        return TempoEstimate(0.0, 0.0, 0.0, autocorr)

    region = autocorr[min_lag : max_lag + 1]
    peak_offset = int(np.argmax(region))
    peak_idx = min_lag + peak_offset
    refined_lag = _parabolic_peak_index(autocorr, peak_idx)
    bpm = float(60.0 * frames_per_sec / refined_lag) if refined_lag > 0 else 0.0

    peak_value = float(region[peak_offset])
    peak_strength = peak_value / float(autocorr[0])
    if len(region) > 1:
        temp = np.array(region, copy=True)
        temp[peak_offset] = -np.inf
        second_peak = float(np.max(temp))
        dominance = max(0.0, peak_value - second_peak) / max(abs(peak_value), 1e-10)
    else:
        dominance = peak_strength
    confidence = float(np.clip(0.7 * peak_strength + 0.3 * dominance, 0.0, 1.0))

    return TempoEstimate(bpm, refined_lag, confidence, autocorr)


def find_beat_times(
    onset_env: np.ndarray,
    sr: int,
    hop_length: int,
    *,
    bpm_hint: float | None = None,
    max_bpm: float = 200.0,
) -> np.ndarray:
    """Detect beat-like peaks from an onset envelope."""
    from scipy.signal import find_peaks

    if len(onset_env) == 0:
        return np.array([], dtype=np.float64)

    smoothed = np.asarray(onset_env, dtype=np.float64)
    if len(smoothed) >= 5:
        smoothed = np.convolve(
            smoothed,
            np.array([0.1, 0.2, 0.4, 0.2, 0.1], dtype=np.float64),
            mode="same",
        )

    frames_per_sec = sr / hop_length
    target_bpm = bpm_hint if bpm_hint and bpm_hint > 0 else max_bpm
    expected_period = max(1.0, 60.0 * frames_per_sec / target_bpm)
    min_distance = max(1, round(expected_period * 0.7))

    prominence = max(float(np.std(smoothed)) * 0.25, float(np.max(smoothed)) * 0.05, 1e-6)
    height = max(
        float(np.median(smoothed)) + float(np.std(smoothed)) * 0.15,
        float(np.max(smoothed)) * 0.2,
        1e-6,
    )
    peaks, _ = find_peaks(
        smoothed,
        distance=min_distance,
        prominence=prominence,
        height=height,
    )

    if len(peaks) == 0 and float(np.max(smoothed)) > 0:
        peaks = np.array([int(np.argmax(smoothed))], dtype=np.int64)

    if bpm_hint and bpm_hint > 0 and len(peaks) > 1:
        interval_frames = 60.0 * frames_per_sec / bpm_hint
        pruned: list[int] = [int(peaks[0])]
        for peak in peaks[1:]:
            if peak - pruned[-1] >= interval_frames * 0.5:
                pruned.append(int(peak))
        peaks = np.asarray(pruned, dtype=np.int64)

    return peaks.astype(np.float64) * hop_length / sr


def sample_interpolated(values: np.ndarray, position: float) -> float:
    """Sample a 1D array at a fractional index using linear interpolation."""
    if len(values) == 0 or position < 0 or position > len(values) - 1:
        return 0.0

    left = int(np.floor(position))
    right = min(left + 1, len(values) - 1)
    alpha = position - left
    return float((1.0 - alpha) * values[left] + alpha * values[right])


def _parabolic_peak_index(values: np.ndarray, peak_idx: int) -> float:
    """Sub-frame refinement around an autocorrelation peak."""
    if peak_idx <= 0 or peak_idx >= len(values) - 1:
        return float(peak_idx)

    y_minus = float(values[peak_idx - 1])
    y_zero = float(values[peak_idx])
    y_plus = float(values[peak_idx + 1])
    denom = y_minus - 2.0 * y_zero + y_plus
    if abs(denom) <= 1e-12:
        return float(peak_idx)

    offset = 0.5 * (y_minus - y_plus) / denom
    offset = max(-1.0, min(1.0, offset))
    return float(peak_idx) + float(offset)
