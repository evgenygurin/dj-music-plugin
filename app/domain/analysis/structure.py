"""Immutable structural section boundaries."""

from __future__ import annotations

from dataclasses import dataclass

_SECTION_KINDS = frozenset(
    {
        "intro",
        "attack",
        "build",
        "pre_drop",
        "drop",
        "peak",
        "breakdown",
        "outro",
        "rise",
        "valley",
        "sustain",
        "ambient",
        "drum_only",
    }
)


@dataclass(frozen=True, slots=True)
class Section:
    kind: str
    start_s: float
    end_s: float
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if self.kind not in _SECTION_KINDS:
            raise ValueError(f"kind must be one of {sorted(_SECTION_KINDS)}")
        if self.start_s < 0 or self.end_s <= self.start_s:
            raise ValueError("end_s must be greater than start_s and start_s non-negative")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s
