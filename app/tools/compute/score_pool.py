from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.application.transition.catalog import UowCandidateCatalog
from app.application.transition.score_pool import ScoreTransitionPool
from app.handlers._context_log import safe_report_progress
from app.schemas.tool_responses import ScorePoolResult
from app.server.di import get_transition_scorer, get_uow
from app.shared.errors import ValidationError
from app.shared.types import JsonIntList


@tool(
    name="transition_score_pool",
    tags={"namespace:compute", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description=(
        "Compute pairwise transition scores for a pool of tracks (N*(N-1) directed "
        "pairs). Used as input to sequence_optimize. Use top_k/components to keep "
        "large-pool responses within client limits."
    ),
    meta={"timeout_s": 300.0},
    timeout=300.0,
)
async def transition_score_pool(
    track_ids: Annotated[
        JsonIntList,
        Field(min_length=0, max_length=500, description="Track IDs to score"),
    ],
    intent: Annotated[
        Literal["maintain", "ramp_up", "cool_down", "contrast"] | None,
        Field(description="Optional transition scoring intent."),
    ] = None,
    top_k: Annotated[
        int | None,
        Field(ge=1, description="Keep only the top_k outgoing pairs per source."),
    ] = None,
    components: Annotated[
        bool,
        Field(description="Include per-component score fields."),
    ] = True,
    uow: Any = Depends(get_uow),
    scorer: Any = Depends(get_transition_scorer),
    ctx: Context = CurrentContext(),
) -> ScorePoolResult:
    try:
        result = await ScoreTransitionPool(UowCandidateCatalog(uow), scorer).execute(
            list(track_ids), intent=intent, top_k=top_k, components=components
        )
    except ValueError as exc:
        details = {}
        if "duplicate" in str(exc):
            details = {"duplicates": [tid for tid in track_ids if track_ids.count(tid) > 1]}
        elif "none of the" in str(exc):
            details = {"missing_track_ids": list(track_ids)}
        raise ValidationError(str(exc), details=details) from exc

    pairs: list[dict[str, float | int]] = []
    for pair in result.pairs:
        item: dict[str, float | int] = {
            "a": pair.source_id,
            "b": pair.target_id,
            "overall": pair.overall,
        }
        if components:
            item.update(
                {
                    "bpm": pair.bpm,
                    "harmonics": pair.harmonics,
                    "energy": pair.energy,
                    "bass": pair.bass,
                    "drums": pair.drums,
                    "vocals": pair.vocals,
                }
            )
        pairs.append(item)
    await safe_report_progress(ctx, progress=result.total_scored_pairs, total=result.total_scored_pairs)
    return ScorePoolResult(
        track_ids=list(track_ids),
        pairs=pairs,
        hard_rejects=result.hard_rejects,
        missing_track_ids=list(result.missing_track_ids),
        total_scored_pairs=result.total_scored_pairs,
    )
