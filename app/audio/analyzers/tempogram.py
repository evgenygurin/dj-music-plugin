"""Tempogram ratio analyzer — librosa tempogram autocorrelation.

Computes: tempogram_ratio_vector — normalized autocorrelation at standard BPM
ratios (0.5x, 1x, 2x, 3x, 4x, etc.). Detects metric complexity.
Straight techno: high peak at 1x. Polyrhythmic: distributed peaks.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext


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
        import librosa

        # Onset envelope shared via ctx (bpm/beat reuse it)
        onset_env = ctx.get_onset_env()
        tempogram = librosa.feature.tempogram(onset_envelope=onset_env, sr=ctx.sr)

        # Estimate dominant tempo
        tempo = librosa.feature.rhythm.tempo(onset_envelope=onset_env, sr=ctx.sr)
        base_bpm = float(tempo[0]) if len(tempo) > 0 else 120.0

        # Sample tempogram at BPM ratio positions
        # tempogram rows correspond to BPM values via lag
        freqs = librosa.tempo_frequencies(tempogram.shape[0], sr=ctx.sr)

        # Mean across time
        acf = np.mean(tempogram, axis=1)

        # Normalize
        acf_max = float(np.max(acf)) if np.max(acf) > 0 else 1.0
        acf_norm = acf / acf_max

        # Sample at ratio positions
        ratios: list[float] = []
        for ratio in self._BPM_RATIOS:
            target_bpm = base_bpm * ratio
            # Find closest frequency bin
            idx = int(np.argmin(np.abs(freqs - target_bpm)))
            ratios.append(round(float(acf_norm[idx]), 4))

        return {"tempogram_ratio_vector": ratios}
