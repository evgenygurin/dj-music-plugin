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

    def __post_init__(self) -> None:
        if not self.parameter or self.end < self.start:
            raise ValueError("invalid automation interval")
        if self.minimum > self.maximum:
            raise ValueError("minimum must not exceed maximum")
        if self.shape not in {"linear", "ease_in", "ease_out"}:
            raise ValueError("unsupported automation shape")

    def value_at(self, position: float) -> float:
        if self.end == self.start:
            ratio = 1.0
        else:
            ratio = min(1.0, max(0.0, (position - self.start) / (self.end - self.start)))
        if self.shape == "ease_in":
            ratio *= ratio
        elif self.shape == "ease_out":
            ratio = 1.0 - (1.0 - ratio) ** 2
        value = self.start_value + (self.end_value - self.start_value) * ratio
        return min(self.maximum, max(self.minimum, value))
