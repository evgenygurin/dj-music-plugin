"""Tonnetz analyzer — librosa tonal centroid features.

Computes: tonnetz_vector — 6D tonal space representation from chroma.
Captures harmonic relationships richer than key alone.
Dimensions: fifths (2), minor thirds (2), major thirds (2).
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.v2.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.v2.audio.core.context import AnalysisContext
from app.v2.audio.core.tonal import compute_pitch_class_chroma, tonal_centroid


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
        import librosa  # noqa: F401

        chroma = compute_pitch_class_chroma(ctx.magnitude, ctx.freqs)
        mean_tonnetz = tonal_centroid(np.mean(chroma, axis=1))
        return {"tonnetz_vector": [round(float(v), 4) for v in mean_tonnetz]}
