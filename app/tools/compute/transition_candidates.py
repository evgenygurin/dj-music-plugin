"""get_transition_candidates — score one track against the analyzed library."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers._context_log import safe_report_progress
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.tool_responses import TransitionCandidate, TransitionCandidatesResult
from app.server.di import get_transition_scorer, get_uow


@tool(
    name="get_transition_candidates",
    tags={"namespace:compute", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description=(
        "Score one source track against the analyzed library and return the "
        "top-k non-rejected candidates sorted by transition quality."
    ),
    meta={"timeout_s": 300.0},
    timeout=300.0,
)
async def get_transition_candidates(
    track_id: Annotated[
        int,
        Field(ge=1, description="Source track ID to score candidates for"),
    ],
    top_k: Annotated[
        int,
        Field(ge=1, le=100, description="Maximum number of candidates to return"),
    ] = 20,
    min_score: Annotated[
        float,
        Field(ge=0.0, le=1.0, description="Minimum overall score threshold"),
    ] = 0.0,
    uow: UnitOfWork = Depends(get_uow),
    scorer: Any = Depends(get_transition_scorer),
    ctx: Context = CurrentContext(),
) -> TransitionCandidatesResult:
    features = await uow.track_features.get_scoring_features_batch([track_id])
    source_features = features.get(track_id)
    if source_features is None:
        return TransitionCandidatesResult(
            from_track_id=track_id,
            total_analyzed=0,
            candidates=[],
            missing_features=True,
        )

    analyzed_page = await uow.tracks.filter(
        where={"has_features": True},
        order=["id"],
        limit=10000,
    )
    candidate_ids = [row.id for row in analyzed_page.items if row.id != track_id]
    if not candidate_ids:
        return TransitionCandidatesResult(
            from_track_id=track_id,
            total_analyzed=0,
            candidates=[],
        )

    candidate_features = await uow.track_features.get_scoring_features_batch(candidate_ids)
    scored: list[tuple[int, TransitionCandidate]] = []
    total = len(candidate_ids)
    for index, candidate_id in enumerate(candidate_ids, start=1):
        target_features = candidate_features.get(candidate_id)
        if target_features is None:
            continue

        score = scorer.score(source_features, target_features)
        if score.hard_reject or score.overall < min_score:
            continue

        best_transition = score.best_transition.name if score.best_transition else None
        scored.append(
            (
                candidate_id,
                TransitionCandidate(
                    track_id=candidate_id,
                    overall=float(score.overall),
                    bpm=getattr(target_features, "bpm", None),
                    key=getattr(target_features, "key_code", None),
                    energy=getattr(target_features, "energy_mean", None),
                    mood=getattr(target_features, "mood", None),
                    best_transition=best_transition,
                ),
            )
        )
        if index % 50 == 0 or index == total:
            await safe_report_progress(ctx, progress=index, total=total)

    scored.sort(key=lambda item: item[1].overall, reverse=True)
    limited = scored[:top_k]
    title_ids = [candidate_id for candidate_id, _candidate in limited]
    tracks = await uow.tracks.get_many(title_ids) if title_ids else {}

    return TransitionCandidatesResult(
        from_track_id=track_id,
        total_analyzed=total,
        candidates=[
            candidate.model_copy(
                update={"title": getattr(tracks.get(candidate_id), "title", "") or ""}
            )
            for candidate_id, candidate in limited
        ],
    )
