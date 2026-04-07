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


def _vectorized_spectral_slope(magnitude: np.ndarray, freqs: np.ndarray) -> np.ndarray:
    """Per-frame spectral slope (dB/octave) — fully vectorized.

    Computes the closed-form OLS slope of log-magnitude (dB) versus log2
    frequency for every frame in one shot. Equivalent to running
    ``np.polyfit(log_freqs, log_mags_frame, 1)[0]`` per frame, but
    avoids the per-frame Python overhead which dominates runtime on
    long signals.

    Skips the DC bin (freq=0). Empty frequency axes return zeros.
    """
    valid = freqs > 0
    if int(np.sum(valid)) < 2:
        return np.zeros(magnitude.shape[1], dtype=np.float64)

    log_freqs = np.log2(freqs[valid])  # shape (n_valid,)
    # dB conversion. Add eps so silent frames don't blow up to -inf.
    log_mags = 20.0 * np.log10(magnitude[valid, :] + 1e-10)  # (n_valid, n_frames)

    # Closed-form linear regression slope:
    #   slope = sum((x - mean_x) * (y - mean_y)) / sum((x - mean_x)^2)
    x = log_freqs
    x_centered = x - x.mean()
    denom = float(np.sum(x_centered**2))
    if denom <= 0:
        return np.zeros(magnitude.shape[1], dtype=np.float64)
    y_centered = log_mags - log_mags.mean(axis=0, keepdims=True)
    slopes: np.ndarray = (x_centered[:, None] * y_centered).sum(axis=0) / denom
    return slopes


def _vectorized_spectral_contrast(
    magnitude: np.ndarray, freqs: np.ndarray, alpha: float = 0.2
) -> np.ndarray:
    """Per-frame mean spectral contrast (dB) — fully vectorized.

    For each band, sorts the in-band magnitudes along the frequency
    axis (one ``np.sort`` per band, batched across frames), then takes
    the dB difference between the mean of the top-alpha and bottom-alpha
    slices. The per-band results are averaged into one contrast value
    per frame.

    Equivalent to calling the original ``_compute_spectral_contrast_frame``
    on each frame independently, but avoids the Python loop over frames.
    """
    n_frames = magnitude.shape[1]
    band_contrasts: list[np.ndarray] = []

    for low_hz, high_hz in _CONTRAST_BANDS_HZ:
        mask = (freqs >= low_hz) & (freqs < high_hz)
        n_in_band = int(np.sum(mask))
        if n_in_band < 2:
            continue

        band_mags = magnitude[mask, :]  # (n_in_band, n_frames)
        sorted_mags = np.sort(band_mags, axis=0)  # ascending along bin axis
        n_alpha = max(1, int(n_in_band * alpha))

        # Top alpha (peak) and bottom alpha (valley) — averaged along bin axis
        peak = sorted_mags[-n_alpha:, :].mean(axis=0)
        valley = sorted_mags[:n_alpha, :].mean(axis=0)

        peak_db = 20.0 * np.log10(peak + 1e-10)
        valley_db = 20.0 * np.log10(valley + 1e-10)
        band_contrasts.append(peak_db - valley_db)

    if not band_contrasts:
        return np.zeros(n_frames, dtype=np.float64)
    result: np.ndarray = np.mean(np.stack(band_contrasts, axis=0), axis=0)
    return result


@register_analyzer
class SpectralAnalyzer(BaseAnalyzer):
    """Spectral analysis using pure numpy FFT."""

    name: ClassVar[str] = "spectral"
    capabilities: ClassVar[frozenset[str]] = frozenset({"spectral"})
    required_packages: ClassVar[list[str]] = []
    # Per-frame slope/contrast loops scale linearly with frame count.
    # Aggregate stats (centroid, rolloff, flatness) converge well within 60s.
    clip_duration_s: ClassVar[float | None] = 60.0

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        """Compute spectral features reusing pre-computed ctx.magnitude/freqs.

        Fully vectorized — no per-frame Python loops. All eight features
        are computed via numpy reductions over the (n_bins, n_frames)
        magnitude matrix shared via the AnalysisContext.
        """
        mag = ctx.magnitude  # shape: (n_bins, n_frames)
        freqs = ctx.freqs  # shape: (n_bins,)
        n_bins = mag.shape[0]

        # ── Centroid, rolloff, flatness, flux (already vectorized) ──

        total_mag = mag.sum(axis=0)  # (n_frames,)
        safe_total = np.where(total_mag > 0, total_mag, 1.0)

        # Centroid: weighted mean frequency per frame
        centroids = (freqs[:, None] * mag).sum(axis=0) / safe_total

        # Rolloff 85 / 95: vectorized via argmax over cumsum threshold
        cumsum = np.cumsum(mag, axis=0)  # (n_bins, n_frames)
        # cumsum >= threshold returns a bool matrix; argmax along axis=0
        # finds the first True per column, equivalent to searchsorted.
        thresh_85 = 0.85 * total_mag  # (n_frames,)
        thresh_95 = 0.95 * total_mag
        idx_85 = np.argmax(cumsum >= thresh_85[None, :], axis=0)
        idx_95 = np.argmax(cumsum >= thresh_95[None, :], axis=0)
        # Frames with total_mag == 0 → both thresholds are 0, argmax → 0
        # which maps to freqs[0] = 0. Acceptable for silent frames.
        idx_85 = np.minimum(idx_85, n_bins - 1)
        idx_95 = np.minimum(idx_95, n_bins - 1)
        rolloff_85 = freqs[idx_85]
        rolloff_95 = freqs[idx_95]

        # Flatness: geometric / arithmetic mean per frame
        log_mag = np.log(mag + 1e-10)
        geo_mean = np.exp(log_mag.mean(axis=0))
        arith_mean = mag.mean(axis=0) + 1e-10
        flatness = geo_mean / arith_mean

        # Flux: L2 norm of frame differences, normalized
        diff = np.diff(mag, axis=1)  # (n_bins, n_frames-1)
        flux = np.linalg.norm(diff, axis=0) / (n_bins + 1e-10)

        # ── Slope and contrast: now vectorized across frames ──
        slopes = _vectorized_spectral_slope(mag, freqs)
        contrasts = _vectorized_spectral_contrast(mag, freqs)

        return {
            "spectral_centroid_hz": float(np.mean(centroids)),
            "spectral_rolloff_85": float(np.mean(rolloff_85)),
            "spectral_rolloff_95": float(np.mean(rolloff_95)),
            "spectral_flatness": float(np.mean(flatness)),
            "spectral_flux_mean": float(np.mean(flux)) if len(flux) > 0 else 0.0,
            "spectral_flux_std": float(np.std(flux)) if len(flux) > 0 else 0.0,
            "spectral_slope": float(np.mean(slopes)),
            "spectral_contrast": float(np.mean(contrasts)),
        }
