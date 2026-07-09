from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext


@register_analyzer
class HpCPExtendedAnalyzer(BaseAnalyzer):
    name: ClassVar[str] = "hpcp_extended"
    level: ClassVar[int] = 6
    required_packages: ClassVar[list[str]] = ["essentia"]

    def analyze(self, audio: np.ndarray, sample_rate: float) -> dict[str, float | None]:
        try:
            import essentia.standard as es
        except ImportError:
            return {"hpcp_entropy": None, "hpcp_crest": None}

        frame_size = 2048
        hop_size = 512
        w = es.Windowing(type="hann")
        spectrum = es.Spectrum()
        spectral_peaks = es.SpectralPeaks(
            maxPeaks=100, magnitudeThreshold=1e-4, minFrequency=80, maxFrequency=4000
        )
        hpcp = es.HPCP(sampleRate=sample_rate)

        hop_generator = es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size)
        hpcp_means = []
        for frame in hop_generator:
            spec = spectrum(w(frame))
            freqs, mags = spectral_peaks(spec)
            hpcp_vals = hpcp(freqs, mags)
            hpcp_means.append(np.mean(hpcp_vals))

        if not hpcp_means:
            return {"hpcp_entropy": None, "hpcp_crest": None}

        hpcp_arr = np.array(hpcp_means)
        prob = hpcp_arr / (hpcp_arr.sum() + 1e-10)
        entropy = float(-np.sum(prob * np.log2(prob + 1e-10)))
        crest = float(hpcp_arr.max() / (hpcp_arr.mean() + 1e-10))

        return {"hpcp_entropy": entropy, "hpcp_crest": crest}

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        return self.analyze(ctx.samples.astype(np.float32, copy=False), ctx.sr)
