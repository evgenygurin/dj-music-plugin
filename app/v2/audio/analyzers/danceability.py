"""Danceability analyzer — essentia DFA algorithm.

Computes: danceability (0.0-3.0 range, Detrended Fluctuation Analysis).
Higher values indicate more regular rhythmic patterns.
Techno average: ~1.5-2.5.
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.v2.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.v2.audio.core.context import AnalysisContext


@register_analyzer
class DanceabilityAnalyzer(BaseAnalyzer):
    """Danceability via essentia's Detrended Fluctuation Analysis."""

    name: ClassVar[str] = "danceability"
    capabilities: ClassVar[frozenset[str]] = frozenset({"rhythm"})
    required_packages: ClassVar[list[str]] = ["essentia"]

    _MAX_DURATION_S: ClassVar[float] = 60.0

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import essentia.standard as es

        # Clip to centre region — DFA on full 400s track is wasteful
        samples = ctx.samples
        max_samples = int(self._MAX_DURATION_S * ctx.sr)
        if len(samples) > max_samples:
            offset = (len(samples) - max_samples) // 2
            samples = samples[offset : offset + max_samples]

        danceability_algo = es.Danceability()
        result, _ = danceability_algo(samples)
        return {"danceability": round(float(result), 4)}
