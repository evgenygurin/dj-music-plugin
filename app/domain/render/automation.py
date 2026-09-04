"""Bounded declarative automation curves."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AutomationCurve:
    parameter: str
    start: float
    end: float
    start_value: float
    end_value: float
    minimum: float
    maximum: float
    shape: str = "linear"

    def value_at(self, position: float) -> float:
        ratio = (
            min(1.0, max(0.0, (position - self.start) / (self.end - self.start)))
            if self.end != self.start
            else 1.0
        )
        value = self.start_value + (self.end_value - self.start_value) * ratio
        return min(self.maximum, max(self.minimum, value))
