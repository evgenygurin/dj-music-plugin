"""transition_score_pool — compute NxN score matrix for a track pool."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.repositories.unit_of_work import UnitOfWork
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
        "pairs). Used as input to sequence_optimize."
    ),
    meta={"timeout_s": 300.0},
    timeout=300.0,
)
async def transition_score_pool(
    track_ids: Annotated[
        JsonIntList,
        Field(min_length=0, max_length=500, description="Track IDs to score"),
    ],
    intent: Annotated[str | None, Field(description="Optional transition intent override")] = None,
    uow: UnitOfWork = Depends(get_uow),
    scorer: Any = Depends(get_transition_scorer),
    ctx: Context = CurrentContext(),
) -> ScorePoolResult:
    if not track_ids:
        return ScorePoolResult(track_ids=[], pairs=[], hard_rejects=0)

    # Audit iter 3: reject duplicate ids explicitly. Prior behaviour
    # produced N*(N-1) pairs counting duplicates as distinct slots,
    # which silently inflated the matrix and disagreed with
    # ``sequence_optimize`` (which deduped on the same input).
    if len(set(track_ids)) != len(track_ids):
        seen: set[int] = set()
        duplicates: list[int] = []
        for tid in track_ids:
            if tid in seen and tid not in duplicates:
                duplicates.append(tid)
            seen.add(tid)
        raise ValidationError(
            f"track_ids contains duplicate id(s): {duplicates}",
            details={"duplicates": duplicates},
        )

    features = await uow.track_features.get_scoring_features_batch(track_ids)
    pairs: list[dict[str, float | int]] = []
    hard_rejects = 0
    total_pairs = len(track_ids) * (len(track_ids) - 1)
    done = 0

    for a in track_ids:
        if a not in features:
            done += len(track_ids) - 1
            continue
        for b in track_ids:
            if a == b:
                continue
            if b not in features:
                done += 1
                continue
            score = scorer.score(features[a], features[b])
            if score.hard_reject:
                hard_rejects += 1
            pairs.append(
                {
                    "a": a,
                    "b": b,
                    "overall": float(score.overall),
                    "bpm": float(score.bpm),
                    "harmonic": float(score.harmonic),
                    "energy": float(score.energy),
                    "spectral": float(score.spectral),
                    "groove": float(score.groove),
                    "timbral": float(score.timbral),
                }
            )
            done += 1
            if done % 50 == 0 or done == total_pairs:
                await ctx.report_progress(progress=done, total=total_pairs)

    return ScorePoolResult(track_ids=track_ids, pairs=pairs, hard_rejects=hard_rejects)
