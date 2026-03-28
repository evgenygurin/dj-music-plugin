"""Spectral analyzer — pure numpy implementation.

Computes: spectral_centroid_hz, spectral_rolloff_85, spectral_rolloff_95,
spectral_flatness, spectral_flux_mean, spectral_flux_std,
spectral_slope, spectral_contrast.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext

# Frequency band edges for spectral contrast (6 octave bands, Hz)
# Similar to librosa defaults: 6 bands from ~200Hz to ~sr/2
_CONTRAST_BANDS_HZ: list[tuple[float, float]] = [
    (200.0, 400.0),
    (400.0, 800.0),
    (800.0, 1600.0),
    (1600.0, 3200.0),
    (3200.0, 6400.0),
    (6400.0, 11025.0),
]


def _compute_spectral_slope(magnitude: np.ndarray, freqs: np.ndarray) -> float:
    """Compute spectral slope via linear regression on log-frequency axis.

    Fits a line to the log-magnitude spectrum vs. log-frequency.
    Result is in dB/octave: how fast the spectrum rolls off.
    """
    # Skip DC (freq=0) and zero magnitudes
    valid = (freqs > 0) & (magnitude > 0)
    if np.sum(valid) < 2:
        return 0.0

    log_freqs = np.log2(freqs[valid])
    log_mags = 20.0 * np.log10(magnitude[valid] + 1e-10)  # dB

    # Linear regression: slope in dB per octave (log2 frequency)
    coeffs = np.polyfit(log_freqs, log_mags, 1)
    return float(coeffs[0])


def _compute_spectral_contrast_frame(
    magnitude: np.ndarray, freqs: np.ndarray, alpha: float = 0.2
) -> float:
    """Compute spectral contrast for one frame: mean peak-valley difference across bands.

    For each frequency band, contrast = peak_dB - valley_dB, where peak/valley
    are computed from the top/bottom alpha fraction of magnitudes in the band.
    Returns the mean contrast across all bands (dB).
    """
    contrasts: list[float] = []

    for low_hz, high_hz in _CONTRAST_BANDS_HZ:
        mask = (freqs >= low_hz) & (freqs < high_hz)
        band_mags = magnitude[mask]

        if len(band_mags) < 2:
            continue

        sorted_mags = np.sort(band_mags)
        n_alpha = max(1, int(len(sorted_mags) * alpha))

        # Peak: mean of top alpha fraction (in dB)
        peak = float(np.mean(sorted_mags[-n_alpha:]))
        # Valley: mean of bottom alpha fraction (in dB)
        valley = float(np.mean(sorted_mags[:n_alpha]))

        peak_db = 20.0 * np.log10(peak + 1e-10)
        valley_db = 20.0 * np.log10(valley + 1e-10)
        contrasts.append(peak_db - valley_db)

    return float(np.mean(contrasts)) if contrasts else 0.0


@register_analyzer
class SpectralAnalyzer(BaseAnalyzer):
    """Spectral analysis using pure numpy FFT."""

    name: ClassVar[str] = "spectral"
    capabilities: ClassVar[frozenset[str]] = frozenset({"spectral"})
    required_packages: ClassVar[list[str]] = []

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        """Compute spectral features from audio signal."""
        samples = ctx.samples
        sr = ctx.sr

        frame_length = 2048
        hop_length = 512
        n_frames = max(1, (len(samples) - frame_length) // hop_length + 1)

        centroids: list[float] = []
        rolloff_85_list: list[float] = []
        rolloff_95_list: list[float] = []
        flatness_list: list[float] = []
        slope_list: list[float] = []
        contrast_list: list[float] = []
        prev_magnitude: np.ndarray | None = None
        flux_list: list[float] = []

        for i in range(n_frames):
            start = i * hop_length
            end = min(start + frame_length, len(samples))
            frame = samples[start:end]

            # Zero-pad if needed
            if len(frame) < frame_length:
                frame = np.pad(frame, (0, frame_length - len(frame)))

            # Apply Hann window
            window = np.hanning(len(frame))
            windowed = frame * window

            # FFT
            fft_vals = np.fft.rfft(windowed)
            magnitude = np.abs(fft_vals)
            freqs = np.fft.rfftfreq(frame_length, d=1.0 / sr)

            # Spectral centroid
            total_mag = float(np.sum(magnitude))
            centroid = float(np.sum(freqs * magnitude) / total_mag) if total_mag > 0 else 0.0
            centroids.append(centroid)

            # Spectral rolloff
            cumsum = np.cumsum(magnitude)
            if total_mag > 0:
                rolloff_85 = float(freqs[np.searchsorted(cumsum, 0.85 * total_mag)])
                rolloff_95 = float(freqs[np.searchsorted(cumsum, 0.95 * total_mag)])
            else:
                rolloff_85 = 0.0
                rolloff_95 = 0.0
            rolloff_85_list.append(rolloff_85)
            rolloff_95_list.append(rolloff_95)

            # Spectral flatness (geometric mean / arithmetic mean)
            mag_positive = magnitude[magnitude > 0]
            if len(mag_positive) > 0 and total_mag > 0:
                log_mean = float(np.mean(np.log(mag_positive + 1e-10)))
                geometric_mean = np.exp(log_mean)
                arithmetic_mean = float(np.mean(magnitude))
                flatness = float(geometric_mean / (arithmetic_mean + 1e-10))
            else:
                flatness = 0.0
            flatness_list.append(flatness)

            # Spectral slope (dB/octave via log-frequency regression)
            slope_list.append(_compute_spectral_slope(magnitude, freqs))

            # Spectral contrast (mean peak-valley difference across bands)
            contrast_list.append(_compute_spectral_contrast_frame(magnitude, freqs))

            # Spectral flux (L2-norm, normalized by bin count — matches essentia Flux)
            if prev_magnitude is not None:
                diff = magnitude - prev_magnitude
                flux = float(np.linalg.norm(diff) / (len(diff) + 1e-10))
                flux_list.append(flux)
            prev_magnitude = magnitude.copy()

        spectral_centroid_hz = float(np.mean(centroids)) if centroids else 0.0
        spectral_rolloff_85 = float(np.mean(rolloff_85_list)) if rolloff_85_list else 0.0
        spectral_rolloff_95 = float(np.mean(rolloff_95_list)) if rolloff_95_list else 0.0
        spectral_flatness = float(np.mean(flatness_list)) if flatness_list else 0.0
        spectral_slope = float(np.mean(slope_list)) if slope_list else 0.0
        spectral_contrast = float(np.mean(contrast_list)) if contrast_list else 0.0

        if flux_list:
            spectral_flux_mean = float(np.mean(flux_list))
            spectral_flux_std = float(np.std(flux_list))
        else:
            spectral_flux_mean = 0.0
            spectral_flux_std = 0.0

        return {
            "spectral_centroid_hz": spectral_centroid_hz,
            "spectral_rolloff_85": spectral_rolloff_85,
            "spectral_rolloff_95": spectral_rolloff_95,
            "spectral_flatness": spectral_flatness,
            "spectral_flux_mean": spectral_flux_mean,
            "spectral_flux_std": spectral_flux_std,
            "spectral_slope": spectral_slope,
            "spectral_contrast": spectral_contrast,
        }
