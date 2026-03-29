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
        """Compute spectral features reusing pre-computed ctx.magnitude/freqs.

        Vectorized where possible — avoids per-frame Python loops for
        centroid, rolloff, flatness, and flux. Slope and contrast still
        need per-frame computation but benefit from shared magnitude.
        """
        mag = ctx.magnitude  # shape: (n_bins, n_frames)
        freqs = ctx.freqs  # shape: (n_bins,)
        n_frames = mag.shape[1]

        # ── Vectorized: centroid, rolloff, flatness, flux ──

        total_mag = mag.sum(axis=0)  # (n_frames,)
        safe_total = np.where(total_mag > 0, total_mag, 1.0)

        # Centroid: weighted mean frequency per frame
        centroids = (freqs[:, None] * mag).sum(axis=0) / safe_total

        # Rolloff 85 / 95: cumulative sum along frequency axis
        cumsum = np.cumsum(mag, axis=0)  # (n_bins, n_frames)
        rolloff_85 = np.zeros(n_frames)
        rolloff_95 = np.zeros(n_frames)
        for i in range(n_frames):
            if total_mag[i] > 0:
                idx_85 = np.searchsorted(cumsum[:, i], 0.85 * total_mag[i])
                idx_95 = np.searchsorted(cumsum[:, i], 0.95 * total_mag[i])
                rolloff_85[i] = freqs[min(idx_85, len(freqs) - 1)]
                rolloff_95[i] = freqs[min(idx_95, len(freqs) - 1)]

        # Flatness: geometric / arithmetic mean per frame
        log_mag = np.log(mag + 1e-10)
        geo_mean = np.exp(log_mag.mean(axis=0))
        arith_mean = mag.mean(axis=0) + 1e-10
        flatness = geo_mean / arith_mean

        # Flux: L2 norm of frame differences, normalized
        diff = np.diff(mag, axis=1)  # (n_bins, n_frames-1)
        n_bins = mag.shape[0]
        flux = np.linalg.norm(diff, axis=0) / (n_bins + 1e-10)

        # ── Per-frame: slope and contrast (use shared magnitude) ──
        slope_list: list[float] = []
        contrast_list: list[float] = []
        for i in range(n_frames):
            frame_mag = mag[:, i]
            slope_list.append(_compute_spectral_slope(frame_mag, freqs))
            contrast_list.append(_compute_spectral_contrast_frame(frame_mag, freqs))

        return {
            "spectral_centroid_hz": float(np.mean(centroids)),
            "spectral_rolloff_85": float(np.mean(rolloff_85)),
            "spectral_rolloff_95": float(np.mean(rolloff_95)),
            "spectral_flatness": float(np.mean(flatness)),
            "spectral_flux_mean": float(np.mean(flux)) if len(flux) > 0 else 0.0,
            "spectral_flux_std": float(np.std(flux)) if len(flux) > 0 else 0.0,
            "spectral_slope": float(np.mean(slope_list)),
            "spectral_contrast": float(np.mean(contrast_list)),
        }
