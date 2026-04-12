"""Tempogram ratio analyzer — librosa tempogram autocorrelation.

Computes: tempogram_ratio_vector — normalized autocorrelation at standard BPM
ratios (0.5x, 1x, 2x, 3x, 4x, etc.). Detects metric complexity.
Straight techno: high peak at 1x. Polyrhythmic: distributed peaks.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from dj_music.audio.analyzers.base import BaseAnalyzer, register_analyzer
from dj_music.audio.core.context import AnalysisContext
from dj_music.audio.core.rhythm import sample_interpolated, tempo_from_onset_autocorrelation


@register_analyzer
class TempogramAnalyzer(BaseAnalyzer):
    """Tempogram ratio via librosa autocorrelation tempogram."""

    name: ClassVar[str] = "tempogram"
    capabilities: ClassVar[frozenset[str]] = frozenset({"rhythm", "tempo"})
    required_packages: ClassVar[list[str]] = ["librosa"]
    # Tempogram autocorrelation aggregated across time — 60s captures the
    # dominant tempo lattice for stable-BPM techno.
    clip_duration_s: ClassVar[float | None] = 60.0

    # Standard BPM ratio multipliers to sample from tempogram
    _BPM_RATIOS: ClassVar[tuple[float, ...]] = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import librosa  # noqa: F401

        # Onset envelope shared via ctx (bpm/beat reuse it)
        onset_env = ctx.get_onset_env()
        estimate = tempo_from_onset_autocorrelation(onset_env, ctx.sr, ctx.params.hop_length)
        base_bpm = estimate.bpm if estimate.bpm > 0 else 120.0
        base_lag = estimate.lag_frames
        if base_lag <= 0:
            base_lag = 60.0 * (ctx.sr / ctx.params.hop_length) / base_bpm

        acf = estimate.autocorrelation
        acf_max = float(np.max(acf)) if len(acf) and float(np.max(acf)) > 0 else 1.0
        acf_norm = acf / acf_max

        # Sample at ratio positions
        ratios: list[float] = []
        for ratio in self._BPM_RATIOS:
            target_lag = base_lag / ratio if ratio > 0 else base_lag
            value = sample_interpolated(acf_norm, target_lag)
            ratios.append(round(float(np.clip(value, 0.0, 1.0)), 4))

        return {"tempogram_ratio_vector": ratios}
