"""Immutable beat and bar alignment primitives."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BeatPosition:
    """A beat timestamp with its ordinal and downbeat role."""

    time_s: float
    index: int
    is_downbeat: bool = False

    def __post_init__(self) -> None:
        if not math.isfinite(self.time_s) or self.time_s < 0:
            raise ValueError("time_s must be finite and non-negative")
        if self.index < 0:
            raise ValueError("index must be non-negative")


@dataclass(frozen=True, slots=True)
class BeatGrid:
    """Validated beatgrid used by transition planning."""

    bpm: float
    beats: tuple[BeatPosition, ...]
    beats_per_bar: int = 4
    phase_s: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.bpm) or self.bpm <= 0:
            raise ValueError("bpm must be positive")
        if not 1 <= self.beats_per_bar <= 16:
            raise ValueError("beats_per_bar must be between 1 and 16")
        if not math.isfinite(self.phase_s) or not 0 <= self.phase_s < self.beat_period_s:
            raise ValueError("phase_s must be within one beat period")
        pairs = zip(self.beats, self.beats[1:], strict=False)
        if any(right.time_s <= left.time_s for left, right in pairs):
            raise ValueError("beat positions must be strictly monotonic")

    @property
    def beat_period_s(self) -> float:
        return 60.0 / self.bpm

    @property
    def downbeats(self) -> tuple[BeatPosition, ...]:
        return tuple(beat for beat in self.beats if beat.is_downbeat)

    @property
    def bar_count(self) -> int:
        return len(self.beats) // self.beats_per_bar
