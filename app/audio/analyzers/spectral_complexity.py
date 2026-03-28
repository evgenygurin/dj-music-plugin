"""SpectralComplexityAnalyzer — count of spectral peaks per frame (essentia)."""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext


@register_analyzer
class SpectralComplexityAnalyzer(BaseAnalyzer):
    """Mean spectral complexity (number of spectral peaks) via essentia."""

    name: ClassVar[str] = "spectral_complexity"
    capabilities: ClassVar[frozenset[str]] = frozenset({"spectral"})
    required_packages: ClassVar[list[str]] = ["essentia"]

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import essentia.standard as es

        w = es.Windowing(type="blackmanharris62")
        spectrum = es.Spectrum()
        sc = es.SpectralComplexity(magnitudeThreshold=0.005, sampleRate=float(ctx.sr))

        frame_size = 2048
        hop_size = 1024
        values: list[float] = []

        for start in range(0, len(ctx.samples) - frame_size, hop_size):
            frame = ctx.samples[start : start + frame_size]
            spec = spectrum(w(frame))
            values.append(float(sc(spec)))

        mean_val = float(np.mean(values)) if values else 0.0
        return {"spectral_complexity_mean": round(mean_val, 4)}
