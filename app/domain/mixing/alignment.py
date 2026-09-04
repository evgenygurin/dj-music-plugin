"""Deterministic beat/phrase alignment for transition candidates."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.analysis.beatgrid import BeatGrid


@dataclass(frozen=True, slots=True)
class AlignmentRequest:
    bars: int
    phase_tolerance_s: float = 0.05
    phrase_tolerance_bars: int = 1

    def __post_init__(self) -> None:
        if self.bars <= 0:
            raise ValueError("bars must be positive")
        if self.phase_tolerance_s < 0:
            raise ValueError("phase_tolerance_s must be non-negative")
        if self.phrase_tolerance_bars < 0:
            raise ValueError("phrase_tolerance_bars must be non-negative")


@dataclass(frozen=True, slots=True)
class AlignmentResult:
    accepted: bool
    beat_error_s: float
    bar_offset: int = 0
    reason: str | None = None


class AlignmentEngine:
    def align(
        self, source: BeatGrid, target: BeatGrid, request: AlignmentRequest
    ) -> AlignmentResult:
        period = max(source.beat_period_s, target.beat_period_s)
        raw = abs(source.phase_s - target.phase_s)
        beat_error = min(raw, period - raw if raw <= period else raw)
        if beat_error > request.phase_tolerance_s:
            return AlignmentResult(False, beat_error, reason="beat_phase_tolerance")
        return AlignmentResult(True, beat_error)
