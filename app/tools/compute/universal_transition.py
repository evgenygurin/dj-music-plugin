"""Small MCP-safe facade for deterministic technical transition checks."""

from __future__ import annotations

from typing import Any

from fastmcp.tools import tool

from app.domain.analysis.snapshot import AnalysisSnapshot
from app.domain.analysis.tempo import TempoHypothesis
from app.domain.mixing.candidate import CandidateTransition
from app.domain.mixing.constraints import HardConstraintValidator


@tool(
    name="validate_transition",
    tags={"namespace:compute", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description="Validate a transition's hard technical tempo constraints without rendering audio.",
)
def validate_transition_request(
    source_bpm: float,
    target_bpm: float,
    duration_s: float,
) -> dict[str, Any]:
    source = AnalysisSnapshot(
        "request-source", "1", tempo_hypotheses=(TempoHypothesis(source_bpm, 1.0),)
    )
    target = AnalysisSnapshot(
        "request-target", "1", tempo_hypotheses=(TempoHypothesis(target_bpm, 1.0),)
    )
    candidate = CandidateTransition.from_values(source, target, source_bpm, target_bpm, duration_s)
    result = HardConstraintValidator().validate(candidate)
    return {
        "accepted": result.accepted,
        "reason": result.reason,
        "drift_beats": result.drift_beats,
        "drift_ms": result.drift_ms,
        "candidate_id": candidate.candidate_id,
    }
