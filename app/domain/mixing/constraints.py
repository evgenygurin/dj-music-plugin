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
    technical_margin: float = 0.0


@dataclass(frozen=True, slots=True)
class HardConstraintValidator:
    max_drift_beats: float = 0.5
    max_drift_ms: float | None = None
    max_tempo_ratio: float = 1.06
    max_phase_error_s: float | None = 0.05

    def validate(self, candidate: CandidateTransition) -> ConstraintResult:
        source = candidate.source_tempo.bpm
        target = candidate.target_tempo.bpm
        ratio = max(source, target) / min(source, target)
        ratio_margin = self.max_tempo_ratio - ratio
        if ratio > self.max_tempo_ratio:
            return ConstraintResult(False, "tempo_ratio", technical_margin=ratio_margin)
        beat_period = 60.0 / target
        elapsed_phase_error_s = abs(60.0 / source - beat_period) * candidate.duration_s
        drift_beats = elapsed_phase_error_s / beat_period
        drift_ms = elapsed_phase_error_s * 1000.0
        drift_margin = self.max_drift_beats - drift_beats
        if drift_beats > self.max_drift_beats:
            return ConstraintResult(False, "tempo_drift", drift_beats, drift_ms, drift_margin)
        if self.max_drift_ms is not None and drift_ms > self.max_drift_ms:
            return ConstraintResult(
                False, "tempo_drift_ms", drift_beats, drift_ms, self.max_drift_ms - drift_ms
            )
        phase_margin = (
            self.max_phase_error_s - abs(candidate.phase_offset_s)
            if self.max_phase_error_s is not None
            else float("inf")
        )
        if phase_margin < 0:
            return ConstraintResult(
                False, "beat_phase_tolerance", drift_beats, drift_ms, phase_margin
            )
        return ConstraintResult(
            True,
            drift_beats=drift_beats,
            drift_ms=drift_ms,
            technical_margin=min(ratio_margin, drift_margin, phase_margin),
        )
