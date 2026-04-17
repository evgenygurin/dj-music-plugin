"""Dynamic complexity analyzer — essentia loudness variance.

Computes: dynamic_complexity (0.0-~10.0) — describes loudness variance.
Low = flat/constant energy (industrial, hard techno).
High = dramatic builds and drops (progressive, melodic).
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.v2.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.v2.audio.core.context import AnalysisContext


@register_analyzer
class DynamicComplexityAnalyzer(BaseAnalyzer):
    """Dynamic complexity via essentia's DynamicComplexity algorithm."""

    name: ClassVar[str] = "dynamic_complexity"
    capabilities: ClassVar[frozenset[str]] = frozenset({"loudness", "dynamics"})
    required_packages: ClassVar[list[str]] = ["essentia"]

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import essentia.standard as es

        dc = es.DynamicComplexity()
        complexity, _loudness_band = dc(ctx.samples)
        return {"dynamic_complexity": round(float(complexity), 4)}
