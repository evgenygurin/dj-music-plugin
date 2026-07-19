"""Multi-deck domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    key_compatibility: dict[str, Any]
    bpm_compatibility: dict[str, Any]
    recommendations: list[str] = field(default_factory=list)


@dataclass
class BandBudget:
    total_lufs: float
    headroom_db: float
    warning: bool


@dataclass
class EnergyBudgetResult:
    total_lufs: float
    headroom_db: float
    per_band: dict[str, BandBudget]
    recommendation: str


@dataclass
class BpmRatioMatch:
    bpm_b: float
    ratio: float
    ratio_label: str
    error_pct: float
    bars_to_align: int
    seconds_to_align: float


@dataclass
class BpmRatioResult:
    bpm_a: float
    matches: list[BpmRatioMatch]
    library_pairs: list[dict[str, Any]]


@dataclass
class TimelineTrack:
    track_id: int
    first_downbeat_ms: float
    bpm: float | None
    sections: list[dict[str, Any]]


@dataclass
class TimelineOverlay:
    tracks: list[TimelineTrack]
    description: str
