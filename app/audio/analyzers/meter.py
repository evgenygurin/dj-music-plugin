from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext


@register_analyzer
class MeterAnalyzer(BaseAnalyzer):
    name: ClassVar[str] = "meter"
    level: ClassVar[int] = 6
    required_packages: ClassVar[list[str]] = ["essentia"]

    def analyze(self, audio: np.ndarray, sample_rate: float) -> dict[str, str | None]:
        try:
            import essentia.standard as es
        except ImportError:
            return {"meter": None}

        try:
            frame_size = 4096
            hop_size = 2048
            w = es.Windowing(type="hann")
            fft = es.FFT()
            loudness_algo = es.Loudness()

            all_loudness: list[float] = []
            for frame in es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size):
                spec = fft(w(frame))
                all_loudness.append(float(loudness_algo(spec)))

            if not all_loudness:
                return {"meter": None}

            loudness_arr = np.array(all_loudness)
            band_ratios_arr = loudness_arr.reshape(-1, 1)

            beatogram_algo = es.Beatogram()
            beatogram_mat = beatogram_algo(loudness_arr, band_ratios_arr)

            meter_algo = es.Meter()
            meter_out = meter_algo(beatogram_mat)
            return {"meter": str(meter_out)}
        except Exception:
            return {"meter": None}

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        return self.analyze(ctx.samples.astype(np.float32, copy=False), ctx.sr)
