"""Loudness analyzer — EBU R128 compliant (ITU-R BS.1770-4).

Computes: integrated_lufs, short_term_lufs_mean, momentary_max,
rms_dbfs, true_peak_db, crest_factor_db, loudness_range_lu.

Uses scipy for K-weighting filter and polyphase oversampling (true peak).
Falls back to simplified approximation if scipy is not available.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext

# ── K-weighting filter coefficients (ITU-R BS.1770-4) ──────────────────
# Two cascaded biquad filters:
#   Stage 1: High-shelf boost (+4 dB at ~1500 Hz) — models head/pinna response
#   Stage 2: High-pass at ~38 Hz — removes infrasonic content
# Coefficients below are for 48 kHz; we recompute for actual sample rate.


def _k_weighting_coefficients(sr: int) -> tuple[np.ndarray, np.ndarray]:
    """Compute K-weighting filter coefficients for given sample rate.

    Returns (b_coeffs, a_coeffs) for cascaded biquad application.
    Each is shape (2, 3) — two stages of second-order sections.
    """

    # Stage 1: Pre-filter (high shelf, +4 dB above ~1500 Hz)
    # Analog prototype from ITU-R BS.1770-4 Table 1
    # s-domain: H(s) = (s² + 2*VH*s + VB) / (s² + 2*VL*s + VB)
    f0 = 1681.974450955533
    q = 0.7071752369554196
    g_db = 3.999843853973347

    k = np.tan(np.pi * f0 / sr)
    vh = 10.0 ** (g_db / 20.0)
    vb = vh**0.499666774155
    a0_1 = 1.0 + k / q + k * k
    b_stage1 = np.array(
        [
            (vh + vb * k / q + k * k) / a0_1,
            2.0 * (k * k - vh) / a0_1,
            (vh - vb * k / q + k * k) / a0_1,
        ]
    )
    a_stage1 = np.array([1.0, 2.0 * (k * k - 1.0) / a0_1, (1.0 - k / q + k * k) / a0_1])

    # Stage 2: High-pass at ~38 Hz (RLB weighting)
    f0_hp = 38.13547087602444
    q_hp = 0.5003270373238773
    k_hp = np.tan(np.pi * f0_hp / sr)
    a0_2 = 1.0 + k_hp / q_hp + k_hp * k_hp
    b_stage2 = np.array([1.0 / a0_2, -2.0 / a0_2, 1.0 / a0_2])
    a_stage2 = np.array(
        [1.0, 2.0 * (k_hp * k_hp - 1.0) / a0_2, (1.0 - k_hp / q_hp + k_hp * k_hp) / a0_2]
    )

    b_coeffs: np.ndarray = np.stack([b_stage1, b_stage2])
    a_coeffs: np.ndarray = np.stack([a_stage1, a_stage2])
    return b_coeffs, a_coeffs


def _apply_k_weighting(samples: np.ndarray, sr: int) -> np.ndarray:
    """Apply K-weighting filter to audio samples."""
    from scipy.signal import lfilter

    b_coeffs, a_coeffs = _k_weighting_coefficients(sr)

    # Apply two cascaded biquad stages
    filtered = samples.copy()
    for i in range(2):
        filtered = lfilter(b_coeffs[i], a_coeffs[i], filtered)

    return filtered


def _rms_to_lufs(rms_val: float) -> float:
    """Convert RMS of K-weighted signal to LUFS."""
    return float(20.0 * np.log10(rms_val + 1e-10) - 0.691)


def _sliding_window_rms(samples: np.ndarray, window_size: int, hop_size: int) -> np.ndarray:
    """Compute RMS values over a sliding window.

    Returns array of RMS values for each window position.
    """
    n_samples = len(samples)
    if n_samples < window_size or window_size <= 0:
        return np.array([], dtype=np.float64)

    n_windows = (n_samples - window_size) // hop_size + 1
    rms_values = np.empty(n_windows, dtype=np.float64)
    for i in range(n_windows):
        start = i * hop_size
        block = samples[start : start + window_size]
        rms_values[i] = float(np.sqrt(np.mean(block**2)))

    return rms_values


def _compute_true_peak(samples: np.ndarray) -> float:
    """Compute true peak using 4x polyphase oversampling (ITU-R BS.1770-4).

    Inter-sample peaks can exceed the sample values by up to ~3 dB.
    4x oversampling catches these peaks accurately.
    """
    try:
        from scipy.signal import resample_poly

        # 4x oversample using polyphase filter
        oversampled = resample_poly(samples, up=4, down=1)
        return float(np.max(np.abs(oversampled)))
    except ImportError:
        # Fallback: raw sample peak (underestimates by 0.5-3 dB)
        return float(np.max(np.abs(samples)))


def _gated_lufs(
    k_weighted: np.ndarray, sr: int, block_sec: float = 0.4, hop_sec: float = 0.1
) -> float:
    """Compute gated integrated loudness per EBU R128.

    Two-stage gating:
    1. Absolute gate at -70 LUFS — discard silence
    2. Relative gate at -10 LU below ungated mean — discard quiet passages
    """
    block_size = int(block_sec * sr)
    hop_size = int(hop_sec * sr)

    block_rms = _sliding_window_rms(k_weighted, block_size, hop_size)
    if len(block_rms) == 0:
        rms = float(np.sqrt(np.mean(k_weighted**2)))
        return _rms_to_lufs(rms)

    block_lufs = np.array([_rms_to_lufs(float(r)) for r in block_rms])

    # Stage 1: absolute gate at -70 LUFS
    above_abs = block_lufs > -70.0
    if not np.any(above_abs):
        return _rms_to_lufs(float(np.mean(block_rms)))

    # Ungated mean (above absolute threshold)
    ungated_mean = float(np.mean(10.0 ** (block_lufs[above_abs] / 10.0)))
    ungated_lufs = 10.0 * np.log10(ungated_mean + 1e-10)

    # Stage 2: relative gate at -10 LU below ungated
    relative_threshold = ungated_lufs - 10.0
    above_rel = block_lufs > relative_threshold
    if not np.any(above_rel):
        return float(ungated_lufs)

    gated_mean = float(np.mean(10.0 ** (block_lufs[above_rel] / 10.0)))
    return float(10.0 * np.log10(gated_mean + 1e-10))


@register_analyzer
class LoudnessAnalyzer(BaseAnalyzer):
    """EBU R128 loudness measurement.

    Implements:
    - Integrated LUFS with K-weighting + two-stage gating (ITU-R BS.1770-4)
    - Short-term LUFS: mean of 3-second K-weighted sliding windows
    - Momentary max: maximum of 400ms K-weighted sliding windows
    - True peak via 4x polyphase oversampling
    - Loudness Range (LRA) from short-term blocks (10th-95th percentile)
    """

    name: ClassVar[str] = "loudness"
    capabilities: ClassVar[frozenset[str]] = frozenset({"loudness"})
    required_packages: ClassVar[list[str]] = []

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        """Compute loudness metrics from audio signal."""
        samples = ctx.samples
        sr = ctx.sr

        # ── K-weighting ──────────────────────────────────────
        try:
            k_weighted = _apply_k_weighting(samples, sr)
        except ImportError:
            # scipy not available — fall back to unweighted (less accurate)
            k_weighted = samples

        # ── RMS and peak (on original signal) ────────────────
        rms = float(np.sqrt(np.mean(samples**2)))
        rms_dbfs = float(20.0 * np.log10(rms + 1e-10))

        # True peak with 4x oversampling
        true_peak = _compute_true_peak(samples)
        true_peak_db = float(20.0 * np.log10(true_peak + 1e-10))

        # Crest factor: peak-to-RMS ratio in dB
        crest_factor_db = float(true_peak_db - rms_dbfs)

        # ── Integrated LUFS (K-weighted + gated) ─────────────
        integrated_lufs = _gated_lufs(k_weighted, sr)

        # ── Short-term LUFS (EBU R128: 3s window, 1s hop) ───
        short_term_window = int(3.0 * sr)
        short_term_hop = int(1.0 * sr)
        short_term_rms = _sliding_window_rms(k_weighted, short_term_window, short_term_hop)

        if len(short_term_rms) > 0:
            short_term_lufs_values = np.array([_rms_to_lufs(float(r)) for r in short_term_rms])
            short_term_lufs_mean = float(np.mean(short_term_lufs_values))
        else:
            short_term_lufs_mean = integrated_lufs

        # ── Momentary max (EBU R128: 400ms window, 100ms hop) ─
        momentary_window = int(0.4 * sr)
        momentary_hop = int(0.1 * sr)
        momentary_rms = _sliding_window_rms(k_weighted, momentary_window, momentary_hop)

        if len(momentary_rms) > 0:
            momentary_lufs_values = np.array([_rms_to_lufs(float(r)) for r in momentary_rms])
            momentary_max = float(np.max(momentary_lufs_values))
        else:
            momentary_max = integrated_lufs

        # ── Loudness Range (LRA) approximation ───────────────
        # Uses short-term loudness blocks, 10th-95th percentile
        if len(short_term_rms) >= 2:
            st_lufs = np.array([_rms_to_lufs(float(r)) for r in short_term_rms])
            # Apply absolute gate at -70 LUFS
            st_above_gate = st_lufs[st_lufs > -70.0]
            if len(st_above_gate) >= 2:
                sorted_vals = np.sort(st_above_gate)
                idx_10 = max(0, int(len(sorted_vals) * 0.10))
                idx_95 = min(len(sorted_vals) - 1, int(len(sorted_vals) * 0.95))
                loudness_range_lu = float(sorted_vals[idx_95] - sorted_vals[idx_10])
            else:
                loudness_range_lu = 0.0
        else:
            loudness_range_lu = 0.0

        return {
            "integrated_lufs": integrated_lufs,
            "short_term_lufs_mean": short_term_lufs_mean,
            "momentary_max": momentary_max,
            "rms_dbfs": rms_dbfs,
            "true_peak_db": true_peak_db,
            "crest_factor_db": crest_factor_db,
            "loudness_range_lu": loudness_range_lu,
        }
