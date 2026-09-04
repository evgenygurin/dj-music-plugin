"""Configuration provenance metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Provenance:
    source: str
    priority: int
    parameter: str | None = None

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("source must not be empty")
        if self.priority < 0:
            raise ValueError("priority must be non-negative")
