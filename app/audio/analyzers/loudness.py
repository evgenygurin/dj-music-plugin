"""Loudness analyzer — pure numpy implementation (EBU R128 approximation).

Computes: integrated_lufs, short_term_lufs_mean, momentary_max,
rms_dbfs, true_peak_db, crest_factor_db, loudness_range_lu.
"""

from __future__ import annotations

import numpy as np

from app.audio.registry import AnalyzerResult, AudioSignal, BaseAnalyzer


def _rms_to_lufs(rms_val: float) -> float:
    """Convert RMS value to approximate LUFS (simplified K-weighting offset)."""
    return float(20.0 * np.log10(rms_val + 1e-10) - 0.691)


def _sliding_window_rms(samples: np.ndarray, window_size: int, hop_size: int) -> np.ndarray:
    """Compute RMS values over a sliding window using stride tricks.

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


class LoudnessAnalyzer(BaseAnalyzer):
    """Loudness measurement using pure numpy (no external audio libs).

    Implements EBU R128 approximation:
    - Integrated LUFS: overall loudness (simplified K-weighting)
    - Short-term LUFS: mean of 3-second sliding window (EBU R128 short-term)
    - Momentary max: maximum of 400ms sliding window (EBU R128 momentary)
    """

    name = "loudness"
    capabilities = {"loudness"}
    required_packages: list[str] = []

    async def analyze(self, signal: AudioSignal) -> AnalyzerResult:
        """Compute loudness metrics from audio signal."""
        samples = signal.samples
        sr = signal.sample_rate

        if len(samples) == 0:
            return AnalyzerResult(
                analyzer_name=self.name,
                success=False,
                error="Empty audio signal",
            )

        # RMS level
        rms = float(np.sqrt(np.mean(samples**2)))
        rms_dbfs = float(20.0 * np.log10(rms + 1e-10))

        # True peak
        true_peak = float(np.max(np.abs(samples)))
        true_peak_db = float(20.0 * np.log10(true_peak + 1e-10))

        # Integrated LUFS approximation (simplified K-weighting)
        integrated_lufs = _rms_to_lufs(rms)

        # Crest factor: peak-to-RMS ratio in dB
        crest_factor_db = float(true_peak_db - rms_dbfs)

        # ── Short-term LUFS (EBU R128: 3s window, 1s hop) ──
        short_term_window = int(3.0 * sr)
        short_term_hop = int(1.0 * sr)
        short_term_rms = _sliding_window_rms(samples, short_term_window, short_term_hop)

        if len(short_term_rms) > 0:
            short_term_lufs_values = np.array([_rms_to_lufs(float(r)) for r in short_term_rms])
            short_term_lufs_mean = float(np.mean(short_term_lufs_values))
        else:
            # Signal shorter than 3s — use integrated as fallback
            short_term_lufs_mean = integrated_lufs

        # ── Momentary max (EBU R128: 400ms window, 100ms hop) ──
        momentary_window = int(0.4 * sr)
        momentary_hop = int(0.1 * sr)
        momentary_rms = _sliding_window_rms(samples, momentary_window, momentary_hop)

        if len(momentary_rms) > 0:
            momentary_lufs_values = np.array([_rms_to_lufs(float(r)) for r in momentary_rms])
            momentary_max = float(np.max(momentary_lufs_values))
        else:
            # Signal shorter than 400ms — use integrated as fallback
            momentary_max = integrated_lufs

        # ── Loudness Range (LRA) approximation ──
        # Uses the short-term loudness blocks (3s, 1s hop)
        if len(short_term_rms) >= 2:
            st_lufs = np.array([_rms_to_lufs(float(r)) for r in short_term_rms])
            sorted_vals = np.sort(st_lufs)
            idx_10 = max(0, int(len(sorted_vals) * 0.10))
            idx_95 = min(len(sorted_vals) - 1, int(len(sorted_vals) * 0.95))
            loudness_range_lu = float(sorted_vals[idx_95] - sorted_vals[idx_10])
        else:
            loudness_range_lu = 0.0

        return AnalyzerResult(
            analyzer_name=self.name,
            features={
                "integrated_lufs": integrated_lufs,
                "short_term_lufs_mean": short_term_lufs_mean,
                "momentary_max": momentary_max,
                "rms_dbfs": rms_dbfs,
                "true_peak_db": true_peak_db,
                "crest_factor_db": crest_factor_db,
                "loudness_range_lu": loudness_range_lu,
            },
        )
