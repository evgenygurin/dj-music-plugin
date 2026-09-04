"""MCP facade for production transition planning from persisted analysis."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from app.application.transition.plan_request import PlanTransitionRequest, PlanTransitionService
from app.domain.mixing.selection import SelectionPolicy
from app.server.di import get_plan_transition_service


@tool(
    name="plan_transition",
    tags={"namespace:compute", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description=(
        "Plan a transition using persisted universal analysis snapshots and the "
        "feature-flagged production engine. Analysis identities are required; "
        "the tool never fabricates beatgrid or tempo data."
    ),
    meta={"timeout_s": 300.0},
    timeout=300.0,
)
async def plan_transition(
    source_track_id: Annotated[int, Field(ge=1, description="Source track ID")],
    target_track_id: Annotated[int, Field(ge=1, description="Target track ID")],
    source_analysis_identity: Annotated[
        str, Field(min_length=1, description="Persisted source AnalysisSnapshot identity")
    ],
    target_analysis_identity: Annotated[
        str, Field(min_length=1, description="Persisted target AnalysisSnapshot identity")
    ],
    bars: Annotated[int, Field(ge=1, le=64, description="Transition length in bars")] = 8,
    policy: Annotated[
        Literal[
            "best",
            "safest",
            "most_harmonic",
            "most_energetic",
            "most_groovy",
            "most_creative",
            "most_smooth",
            "explicit_profile",
        ],
        Field(description="Deterministic transition selection policy"),
    ] = "best",
    service: PlanTransitionService = Depends(get_plan_transition_service),
) -> dict[str, Any]:
    result = await service.execute(
        PlanTransitionRequest(
            source_track_id,
            target_track_id,
            source_analysis_identity,
            target_analysis_identity,
            bars,
            SelectionPolicy(policy),
        )
    )
    return _result_payload(result)


def _result_payload(result: Any) -> dict[str, Any]:
    decision = result.value
    plan = getattr(decision, "selected", getattr(decision, "plan", decision))
    payload: dict[str, Any] = {
        "value": "planned",
        "execution_identity": getattr(plan, "execution_identity", None),
    }
    if hasattr(decision, "score"):
        payload.update(
            {
                "score": float(decision.score),
                "technical_margin": float(decision.technical_margin),
                "recipe": getattr(getattr(plan, "recipe", None), "kind", None),
                "alternatives": list(decision.alternatives),
                "rejected": [list(item) for item in decision.rejected],
                "diagnostics": list(decision.diagnostics),
                "dimension_scores": dict(decision.dimension_scores),
            }
        )
    if result.comparison is not None:
        payload["shadow_comparison"] = {
            "technical_parity": result.comparison.technical_parity,
            "score_delta": result.comparison.score_delta,
            "legacy_candidate": result.comparison.legacy_candidate,
            "new_candidate": result.comparison.new_candidate,
            "recipe_parity": result.comparison.recipe_parity,
            "rejection_parity": result.comparison.rejection_parity,
            "technical_margin_delta": result.comparison.technical_margin_delta,
            "dimension_deltas": dict(result.comparison.dimension_deltas),
        }
    return payload
