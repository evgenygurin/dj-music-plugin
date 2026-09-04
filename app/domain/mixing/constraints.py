"""Absolute technical validation for transition candidates."""

from __future__ import annotations

from dataclasses import dataclass

from .candidate import CandidateTransition


@dataclass(frozen=True, slots=True)
class ConstraintResult:
    accepted: bool
    reason: str | None = None
    drift_beats: float = 0.0
    drift_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class HardConstraintValidator:
    max_drift_beats: float = 1.0
    max_drift_ms: float | None = None
    max_tempo_ratio: float = 1.06

    def validate(self, candidate: CandidateTransition) -> ConstraintResult:
        source = candidate.source_tempo.bpm
        target = candidate.target_tempo.bpm
        ratio = max(source, target) / min(source, target)
        if ratio > self.max_tempo_ratio:
            return ConstraintResult(False, "tempo_ratio")
        beat_period = 60.0 / target
        elapsed_phase_error_s = abs(60.0 / source - beat_period) * candidate.duration_s
        drift_beats = elapsed_phase_error_s / beat_period
        drift_ms = elapsed_phase_error_s * 1000.0
        if drift_beats > self.max_drift_beats:
            return ConstraintResult(False, "tempo_drift", drift_beats, drift_ms)
        if self.max_drift_ms is not None and drift_ms > self.max_drift_ms:
            return ConstraintResult(False, "tempo_drift_ms", drift_beats, drift_ms)
        return ConstraintResult(True, drift_beats=drift_beats, drift_ms=drift_ms)
