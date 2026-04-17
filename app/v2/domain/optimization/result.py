"""Optimization result dataclass."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OptimizationResult:
    """Result of set optimization — ordered track IDs with quality metrics."""

    track_order: list[int]
    quality_score: float
    generations: int | None = None
    algorithm: str = "greedy"
