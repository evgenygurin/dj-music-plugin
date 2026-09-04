"""Small MCP-safe facade for deterministic technical transition checks."""

from __future__ import annotations

from typing import Any

from fastmcp.tools import tool

from app.application.transition.validation import TransitionValidation


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
    result = TransitionValidation().validate(source_bpm, target_bpm, duration_s)
    return {
        "accepted": result.accepted,
        "reason": result.reason,
        "drift_beats": result.drift_beats,
        "drift_ms": result.drift_ms,
        "candidate_id": result.candidate_id,
    }
