"""sequence_optimize — GA or greedy track-ordering optimizer."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.repositories.unit_of_work import UnitOfWork
from app.schemas.tool_responses import SequenceOptimizeResult
from app.server.di import get_optimizer, get_transition_scorer, get_uow
from app.shared.types import JsonIntList, JsonIntListOrNone


@tool(
    name="sequence_optimize",
    tags={"namespace:compute", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": False},
    description=(
        "Find optimal track ordering via GA or greedy. Supports pinned/excluded "
        "tracks + template-aware fitness. Returns ordering + quality score."
    ),
    meta={"timeout_s": 300.0},
    timeout=300.0,
)
async def sequence_optimize(
    track_ids: Annotated[
        JsonIntList, Field(min_length=2, max_length=500, description="Pool of track IDs")
    ],
    algorithm: Annotated[
        Literal["ga", "greedy"], Field(description="Optimization algorithm")
    ] = "ga",
    template: Annotated[
        str | None, Field(description="Set template name (for template-aware fitness)")
    ] = None,
    pinned: Annotated[JsonIntListOrNone, Field(description="Must-include track IDs")] = None,
    excluded: Annotated[JsonIntListOrNone, Field(description="Banned track IDs")] = None,
    uow: UnitOfWork = Depends(get_uow),
    scorer=Depends(get_transition_scorer),
    optimizer_builder=Depends(get_optimizer),
    ctx: Context = CurrentContext(),
) -> SequenceOptimizeResult:
    features = await uow.track_features.get_scoring_features_batch(track_ids)
    features_list = [features.get(tid) for tid in track_ids]

    optimizer = optimizer_builder(algorithm=algorithm, scorer=scorer)

    async def _progress(gen: int, score: float) -> None:
        await ctx.report_progress(progress=gen, total=100, message=f"best={score:.3f}")

    result = optimizer.optimize(
        tracks=features_list,
        track_ids=track_ids,
        pinned=set(pinned or []),
        excluded=set(excluded or []),
        template=None,  # Phase 6 resolves template definition
        moods=None,
        on_progress=lambda g, s: None,
    )

    return SequenceOptimizeResult(
        track_order=list(result.track_order),
        quality_score=float(result.quality_score),
        algorithm=algorithm,
        generations=result.generations or 0,
    )
