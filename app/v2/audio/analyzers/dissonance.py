"""Dissonance analyzer — essentia spectral dissonance.

Computes: dissonance_mean (0.0-1.0) — mean spectral dissonance across frames.
Low values = clean harmonics (melodic techno), high values = harsh texture (industrial).
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.v2.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.v2.audio.core.context import AnalysisContext


@register_analyzer
class DissonanceAnalyzer(BaseAnalyzer):
    """Mean spectral dissonance via essentia."""

    name: ClassVar[str] = "dissonance"
    capabilities: ClassVar[frozenset[str]] = frozenset({"spectral", "harmony"})
    required_packages: ClassVar[list[str]] = ["essentia"]

    _MAX_DURATION_S: ClassVar[float] = 60.0

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import essentia.standard as es

        # Frame-wise spectral peaks + dissonance
        w = es.Windowing(type="hann")
        spectrum = es.Spectrum()
        peaks = es.SpectralPeaks(sampleRate=ctx.sr)
        dissonance = es.Dissonance()

        frame_size = 2048
        hop_size = 1024

        # Clip to centre region for performance
        samples = ctx.samples
        max_samples = int(self._MAX_DURATION_S * ctx.sr)
        if len(samples) > max_samples:
            offset = (len(samples) - max_samples) // 2
            samples = samples[offset : offset + max_samples]

        dissonance_values: list[float] = []

        for start in range(0, len(samples) - frame_size, hop_size):
            frame = samples[start : start + frame_size]
            windowed = w(frame)
            spec = spectrum(windowed)
            freqs, mags = peaks(spec)
            if len(freqs) >= 2:
                diss = dissonance(freqs, mags)
                dissonance_values.append(float(diss))

        mean_diss = float(np.mean(dissonance_values)) if dissonance_values else 0.0
        return {"dissonance_mean": round(mean_diss, 4)}
