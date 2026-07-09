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

    def analyze(self, audio: np.ndarray, sample_rate: float) -> dict[str, str]:
        try:
            import essentia.standard as es
        except ImportError:
            return {"meter": "4/4"}

        try:
            rhythm_extractor = es.RhythmExtractor2013(method="multifeature")
            bpm, beats, _, _, _ = rhythm_extractor(audio)
            if bpm == 0 or len(beats) < 4:
                return {"meter": "4/4"}
            intervals = np.diff(beats)
            median_interval = np.median(intervals)
            bar_length = median_interval * 4
            strengths: dict[str, float] = {}
            for denom, label in [(4, "4/4"), (3, "3/4"), (5, "5/4"), (6, "6/8"), (7, "7/8")]:
                tempo_seconds = 60.0 / (bpm / (denom / 4.0))
                acc = 0.0
                for i in range(len(beats) - denom):
                    acc += 1.0 / (1.0 + abs((beats[i + denom] - beats[i]) - bar_length))
                strengths[label] = acc / max(len(beats) - denom, 1)
            best = max(strengths, key=strengths.get)
            return {"meter": best if strengths[best] > 0.01 else "4/4"}
        except Exception:
            return {"meter": "4/4"}

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        return self.analyze(ctx.samples.astype(np.float32, copy=False), ctx.sr)
