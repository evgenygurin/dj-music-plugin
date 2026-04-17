"""BpmHistogramAnalyzer — rhythmic stability from beat intervals (essentia)."""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.v2.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.v2.audio.core.context import AnalysisContext


@register_analyzer
class BpmHistogramAnalyzer(BaseAnalyzer):
    """BPM histogram descriptors from beat intervals. Nearly free — reuses BeatDetector output."""

    name: ClassVar[str] = "bpm_histogram"
    capabilities: ClassVar[frozenset[str]] = frozenset({"rhythm"})
    required_packages: ClassVar[list[str]] = ["essentia"]
    depends_on: ClassVar[frozenset[str]] = frozenset({"beat"})

    def _extract(
        self, ctx: AnalysisContext, *, prior_results: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        import essentia.standard as es

        beats_intervals = (prior_results or {}).get("beats_intervals")
        if not beats_intervals or len(beats_intervals) < 4:
            return {
                "bpm_histogram_first_peak_weight": None,
                "bpm_histogram_second_peak_bpm": None,
                "bpm_histogram_second_peak_weight": None,
            }

        bhd = es.BpmHistogramDescriptors()
        intervals = np.array(beats_intervals, dtype=np.float32)
        _p1_bpm, p1_weight, _p1_spread, p2_bpm, p2_weight, _p2_spread, _hist = bhd(intervals)

        return {
            "bpm_histogram_first_peak_weight": round(float(p1_weight), 4),
            "bpm_histogram_second_peak_bpm": round(float(p2_bpm), 2),
            "bpm_histogram_second_peak_weight": round(float(p2_weight), 4),
        }
