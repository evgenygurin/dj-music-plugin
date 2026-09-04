"""Application use case for deterministic transition validation."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.analysis.snapshot import AnalysisSnapshot
from app.domain.analysis.tempo import TempoHypothesis
from app.domain.mixing.candidate import CandidateTransition
from app.domain.mixing.constraints import HardConstraintValidator


@dataclass(frozen=True, slots=True)
class TransitionValidationResult:
    accepted: bool
    reason: str | None
    drift_beats: float
    drift_ms: float
    candidate_id: str


class TransitionValidation:
    """Validate a transition request without exposing domain wiring to adapters."""

    def __init__(self, validator: HardConstraintValidator | None = None) -> None:
        self._validator = validator or HardConstraintValidator()

    def validate(
        self,
        source_bpm: float,
        target_bpm: float,
        duration_s: float,
    ) -> TransitionValidationResult:
        source = AnalysisSnapshot(
            "request-source", "1", tempo_hypotheses=(TempoHypothesis(source_bpm, 1.0),)
        )
        target = AnalysisSnapshot(
            "request-target", "1", tempo_hypotheses=(TempoHypothesis(target_bpm, 1.0),)
        )
        candidate = CandidateTransition.from_values(
            source, target, source_bpm, target_bpm, duration_s
        )
        result = self._validator.validate(candidate)
        return TransitionValidationResult(
            result.accepted,
            result.reason,
            result.drift_beats,
            result.drift_ms,
            candidate.candidate_id,
        )
