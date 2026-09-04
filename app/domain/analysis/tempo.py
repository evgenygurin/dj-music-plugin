"""Immutable tempo hypotheses for the universal DJ domain."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TempoHypothesis:
    """One plausible musical tempo, including octave ambiguity."""

    bpm: float
    confidence: float
    source: str = "unknown"

    def __post_init__(self) -> None:
        if not math.isfinite(self.bpm) or not 20.0 <= self.bpm <= 300.0:
            raise ValueError("bpm must be finite and between 20 and 300")
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not self.source.strip():
            raise ValueError("source must not be empty")

    def variants(self) -> tuple[float, float, float]:
        """Return the standard 0.5x, 1x and 2x tempo interpretations."""
        return (self.bpm * 0.5, self.bpm, self.bpm * 2.0)
