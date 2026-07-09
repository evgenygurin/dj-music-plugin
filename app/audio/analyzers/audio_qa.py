from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext


@register_analyzer
class AudioQAAnalyzer(BaseAnalyzer):
    name: ClassVar[str] = "audio_qa"
    level: ClassVar[int] = 6
    required_packages: ClassVar[list[str]] = ["essentia"]

    def analyze(self, audio: np.ndarray, sample_rate: float) -> dict[str, bool | None]:
        try:
            import essentia.standard as es
        except ImportError:
            return {"click_detected": None, "saturation_detected": None}

        click_detector = es.ClickDetector(frameSize=2048, hopSize=512)
        starts, _ = click_detector(audio)
        click_detected = bool(len(starts) > 0)

        saturation_detector = es.SaturationDetector(frameSize=2048, hopSize=512)
        sat_starts, _ = saturation_detector(audio)
        saturation_detected = bool(len(sat_starts) > 0)

        return {"click_detected": click_detected, "saturation_detected": saturation_detected}

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        return self.analyze(ctx.samples.astype(np.float32, copy=False), ctx.sr)
