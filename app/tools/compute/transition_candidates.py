"""get_transition_candidates — application boundary for candidate discovery."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.application.transition.candidates import GenerateTransitionCandidates
from app.application.transition.catalog import UowCandidateCatalog
from app.handlers._context_log import safe_report_progress
from app.schemas.tool_responses import TransitionCandidate, TransitionCandidatesResult
from app.server.di import get_transition_candidate_generator


@tool(
    name="get_transition_candidates",
    tags={"namespace:compute", "namespace:internal", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description=(
        "INTERNAL / PROGRAMMATIC ONLY — discovers and ranks transition candidates "
        "through the universal application use case."
    ),
    meta={"timeout_s": 300.0},
    timeout=300.0,
)
async def get_transition_candidates(
    track_id: Annotated[int, Field(ge=1, description="Source track ID")],
    top_k: Annotated[int, Field(ge=1, le=100, description="Maximum candidates")] = 20,
    min_score: Annotated[float, Field(ge=0.0, le=1.0, description="Minimum score")] = 0.0,
    generator: GenerateTransitionCandidates = Depends(get_transition_candidate_generator),
    uow: Any = None,
    scorer: Any = None,
    ctx: Context = CurrentContext(),
) -> TransitionCandidatesResult:
    # Direct-call compatibility keeps existing unit tests/headless callers working;
    # MCP runtime always supplies the application use case through DI.
    if not hasattr(generator, "execute"):
        if uow is None or scorer is None:
            raise RuntimeError("candidate generator or legacy test dependencies are required")
        generator = GenerateTransitionCandidates(UowCandidateCatalog(uow), scorer)

    summaries = await generator.execute(track_id, top_k=top_k, min_score=min_score)
    candidates = [
        TransitionCandidate(
            track_id=item.track_id,
            overall=item.overall,
            bpm=item.bpm,
            key=item.key,
            energy=item.energy,
            mood=item.mood,
            best_transition=item.best_transition,
            title=item.title,
        )
        for item in summaries
    ]
    await safe_report_progress(ctx, progress=len(candidates), total=len(candidates))
    return TransitionCandidatesResult(
        from_track_id=track_id,
        total_analyzed=len(candidates),
        candidates=candidates,
        missing_features=not summaries,
    )
