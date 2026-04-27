"""Tonal helpers shared by key, tonnetz, phrase, and MFCC analyzers."""

from __future__ import annotations

import numpy as np


def compute_pitch_class_chroma(magnitude: np.ndarray, freqs: np.ndarray) -> np.ndarray:
    """Project an STFT magnitude spectrogram into 12 pitch classes."""
    if magnitude.ndim != 2:
        msg = "compute_pitch_class_chroma expects a 2D magnitude matrix"
        raise ValueError(msg)

    n_frames = magnitude.shape[1]
    chroma = np.zeros((12, n_frames), dtype=np.float64)

    valid = (freqs > 0.0) & np.isfinite(freqs)
    if not np.any(valid):
        return chroma

    freq_values = freqs[valid]
    midi = 69.0 + 12.0 * np.log2(freq_values / 440.0)
    pitch_classes = np.mod(np.rint(midi).astype(np.int64), 12)
    power = np.asarray(magnitude[valid], dtype=np.float64) ** 2

    for row_index, pitch_class in enumerate(pitch_classes):
        chroma[pitch_class] += power[row_index]

    frame_sums = np.sum(chroma, axis=0, keepdims=True)
    nonzero = frame_sums > 0
    chroma[:, nonzero[0]] = chroma[:, nonzero[0]] / frame_sums[:, nonzero[0]]
    return chroma


def tonal_centroid(chroma_vector: np.ndarray) -> np.ndarray:
    """Project a 12D chroma vector into a 6D tonal-centroid space."""
    chroma = np.asarray(chroma_vector, dtype=np.float64)
    total = float(np.sum(chroma))
    if total <= 0:
        return np.zeros(6, dtype=np.float64)

    chroma = chroma / total
    pitch_classes = np.arange(12, dtype=np.float64)
    basis = np.vstack(
        [
            np.cos(7.0 * np.pi * pitch_classes / 6.0),
            np.sin(7.0 * np.pi * pitch_classes / 6.0),
            np.cos(3.0 * np.pi * pitch_classes / 2.0),
            np.sin(3.0 * np.pi * pitch_classes / 2.0),
            np.cos(2.0 * np.pi * pitch_classes / 3.0),
            np.sin(2.0 * np.pi * pitch_classes / 3.0),
        ]
    )
    centroid = basis @ chroma
    return np.clip(centroid, -1.5, 1.5)


def compute_mfcc(
    magnitude: np.ndarray,
    freqs: np.ndarray,
    sr: int,
    *,
    n_mfcc: int,
    n_mels: int = 40,
) -> np.ndarray:
    """Compute MFCCs from an STFT magnitude spectrogram."""
    from scipy.fft import dct

    power = np.asarray(magnitude, dtype=np.float64) ** 2
    if power.ndim != 2:
        msg = "compute_mfcc expects a 2D magnitude matrix"
        raise ValueError(msg)

    filterbank = mel_filterbank(freqs=freqs, sr=sr, n_mels=n_mels)
    mel_spec = filterbank @ power
    mel_spec = np.maximum(mel_spec, 1e-10)
    log_mel = np.log(mel_spec)
    coeffs = dct(log_mel, type=2, axis=0, norm="ortho")[:n_mfcc]
    return np.asarray(coeffs)


def mel_filterbank(freqs: np.ndarray, sr: int, *, n_mels: int) -> np.ndarray:
    """Build a triangular mel filterbank aligned to FFT bin frequencies."""
    nyquist = sr / 2.0
    mel_min = hz_to_mel(0.0)
    mel_max = hz_to_mel(nyquist)
    mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
    hz_points = np.asarray(mel_to_hz(mel_points))

    filterbank = np.zeros((n_mels, len(freqs)), dtype=np.float64)
    for mel_bin in range(n_mels):
        left_hz = hz_points[mel_bin]
        center_hz = hz_points[mel_bin + 1]
        right_hz = hz_points[mel_bin + 2]

        left = (freqs >= left_hz) & (freqs <= center_hz)
        right = (freqs >= center_hz) & (freqs <= right_hz)

        if center_hz > left_hz:
            filterbank[mel_bin, left] = (freqs[left] - left_hz) / (center_hz - left_hz)
        if right_hz > center_hz:
            filterbank[mel_bin, right] = (right_hz - freqs[right]) / (right_hz - center_hz)

    return filterbank


def hz_to_mel(freq_hz: float | np.ndarray) -> float | np.ndarray:
    return 2595.0 * np.log10(1.0 + np.asarray(freq_hz) / 700.0)


def mel_to_hz(mel: float | np.ndarray) -> float | np.ndarray:
    return 700.0 * (10.0 ** (np.asarray(mel) / 2595.0) - 1.0)
