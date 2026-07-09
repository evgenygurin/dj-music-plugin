"""Multi-deck domain models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StemLayer:
    track_id: int
    stem_name: str


@dataclass
class BandScore:
    score: float
    clash: bool
    culprits: list[str] = field(default_factory=list)


@dataclass
class CompatibilityResult:
    overall_score: float
    hard_reject: bool
    per_band: dict[str, BandScore]
    key_compatibility: dict
    bpm_compatibility: dict
    recommendations: list[str] = field(default_factory=list)
