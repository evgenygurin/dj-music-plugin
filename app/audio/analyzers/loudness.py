"""Loudness analyzer — pure numpy implementation.

Computes: integrated_lufs (approximation), rms_dbfs, true_peak_db,
crest_factor_db, loudness_range_lu.
"""

from __future__ import annotations

import numpy as np

from app.audio.registry import AnalyzerResult, AudioSignal, BaseAnalyzer


class LoudnessAnalyzer(BaseAnalyzer):
    """Loudness measurement using pure numpy (no external audio libs)."""

    name = "loudness"
    capabilities = {"loudness"}
    required_packages: list[str] = []

    async def analyze(self, signal: AudioSignal) -> AnalyzerResult:
        """Compute loudness metrics from audio signal."""
        samples = signal.samples

        if len(samples) == 0:
            return AnalyzerResult(
                analyzer_name=self.name,
                success=False,
                error="Empty audio signal",
            )

        # RMS level
        rms = float(np.sqrt(np.mean(samples**2)))
        rms_dbfs = 20.0 * np.log10(rms + 1e-10)

        # True peak
        true_peak = float(np.max(np.abs(samples)))
        true_peak_db = 20.0 * np.log10(true_peak + 1e-10)

        # LUFS approximation (simplified K-weighting)
        # Real LUFS uses K-weighting filter + gating. This is a rough estimate.
        integrated_lufs = float(rms_dbfs - 0.691)

        # Crest factor: peak-to-RMS ratio in dB
        crest_factor_db = float(true_peak_db - rms_dbfs)

        # Loudness Range (LRA) approximation
        # Split into short-term blocks (3s with 2s overlap = 1s hop)
        block_size = int(3.0 * signal.sample_rate)
        hop_size = int(1.0 * signal.sample_rate)

        if block_size > 0 and len(samples) >= block_size:
            block_loudnesses = []
            for start in range(0, len(samples) - block_size + 1, hop_size):
                block = samples[start : start + block_size]
                block_rms = float(np.sqrt(np.mean(block**2)))
                block_dbfs = 20.0 * np.log10(block_rms + 1e-10)
                block_loudnesses.append(block_dbfs)

            if len(block_loudnesses) >= 2:
                sorted_vals = sorted(block_loudnesses)
                # LRA = difference between 95th and 10th percentile
                idx_10 = max(0, int(len(sorted_vals) * 0.10))
                idx_95 = min(len(sorted_vals) - 1, int(len(sorted_vals) * 0.95))
                loudness_range_lu = float(sorted_vals[idx_95] - sorted_vals[idx_10])
            else:
                loudness_range_lu = 0.0
        else:
            loudness_range_lu = 0.0

        return AnalyzerResult(
            analyzer_name=self.name,
            features={
                "integrated_lufs": float(integrated_lufs),
                "rms_dbfs": float(rms_dbfs),
                "true_peak_db": float(true_peak_db),
                "crest_factor_db": float(crest_factor_db),
                "loudness_range_lu": float(loudness_range_lu),
            },
        )
