"""Tonnetz analyzer — librosa tonal centroid features.

Computes: tonnetz_vector — 6D tonal space representation from chroma.
Captures harmonic relationships richer than key alone.
Dimensions: fifths (2), minor thirds (2), major thirds (2).
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext


@register_analyzer
class TonnetzAnalyzer(BaseAnalyzer):
    """6D tonal centroid features via librosa tonnetz."""

    name: ClassVar[str] = "tonnetz"
    capabilities: ClassVar[frozenset[str]] = frozenset({"harmony", "tonal"})
    required_packages: ClassVar[list[str]] = ["librosa"]
    # librosa.feature.tonnetz computes chroma_cqt internally — same scaling
    # as KeyDetector. Mean-across-time aggregate is stable on 60s.
    clip_duration_s: ClassVar[float | None] = 60.0

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import librosa

        tonnetz = librosa.feature.tonnetz(y=ctx.samples, sr=ctx.sr)
        # Mean across time → 6D vector
        mean_tonnetz = np.mean(tonnetz, axis=1)
        return {"tonnetz_vector": [round(float(v), 4) for v in mean_tonnetz]}
