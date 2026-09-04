"""Immutable DJ cue metadata."""

from __future__ import annotations

from dataclasses import dataclass

_CUE_KINDS = frozenset(
    {
        "mix_in",
        "mix_out",
        "drop",
        "breakdown",
        "buildup",
        "vocal_in",
        "vocal_out",
        "loop_in",
        "loop_out",
        "custom",
    }
)


@dataclass(frozen=True, slots=True)
class CuePoint:
    time_s: float
    kind: str
    bar: int | None = None
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if self.time_s < 0:
            raise ValueError("time_s must be non-negative")
        if self.kind not in _CUE_KINDS:
            raise ValueError(f"kind must be one of {sorted(_CUE_KINDS)}")
        if self.bar is not None and self.bar < 0:
            raise ValueError("bar must be non-negative")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
