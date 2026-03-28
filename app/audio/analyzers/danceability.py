"""Danceability analyzer — essentia DFA algorithm.

Computes: danceability (0.0-3.0 range, Detrended Fluctuation Analysis).
Higher values indicate more regular rhythmic patterns.
Techno average: ~1.5-2.5.
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext


@register_analyzer
class DanceabilityAnalyzer(BaseAnalyzer):
    """Danceability via essentia's Detrended Fluctuation Analysis."""

    name: ClassVar[str] = "danceability"
    capabilities: ClassVar[frozenset[str]] = frozenset({"rhythm"})
    required_packages: ClassVar[list[str]] = ["essentia"]

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import essentia.standard as es

        danceability_algo = es.Danceability()
        result, _ = danceability_algo(ctx.samples)
        return {"danceability": round(float(result), 4)}
