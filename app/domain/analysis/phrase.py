"""Immutable phrase boundaries."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Phrase:
    start_s: float
    end_s: float
    start_bar: int
    end_bar: int
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if self.start_s < 0 or self.end_s <= self.start_s:
            raise ValueError("end_s must be greater than start_s and start_s non-negative")
        if self.start_bar < 0 or self.end_bar <= self.start_bar:
            raise ValueError("end_bar must be greater than start_bar")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    @property
    def bar_count(self) -> int:
        return self.end_bar - self.start_bar
