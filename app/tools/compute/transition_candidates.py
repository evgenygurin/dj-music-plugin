"""get_transition_candidates — score source track against all analyzed tracks."""

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
from app.shared.errors import ValidationError


@tool(
    name="get_transition_candidates",
    tags={"namespace:compute", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description=(
        "Score the source track against the entire analyzed library and return "
        "the top-k candidates sorted by transition quality. Hard rejects are "
        "excluded from the result. Use when the user says their library has "
        '"огромная база треков" but the system only picks "ближайшие какие-то треки".'
    ),
    timeout=300.0,
)
async def get_transition_candidates(
    track_id: Annotated[
        int,
        Field(ge=1, description="Source track ID to score candidates for"),
    ],
    top_k: Annotated[
        int,
        Field(ge=1, le=100, description="Max candidates to return"),
    ] = 20,
    min_score: Annotated[
        float,
        Field(
            ge=0.0, le=1.0,
            description="Minimum overall score threshold (0.0 = no threshold)",
        ),
    ] = 0.0,
    uow: UnitOfWork = Depends(get_uow),
    scorer: Any = Depends(get_transition_scorer),
    ctx: Context = CurrentContext(),
) -> TransitionCandidatesResult:
    feats = await uow.track_features.get_scoring_features_batch([track_id])
    src_feat = feats.get(track_id)
    if src_feat is None:
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
    all_ids = [t.id for t in analyzed_page.items if t.id != track_id]
    if not all_ids:
        return TransitionCandidatesResult(
            from_track_id=track_id,
            total_analyzed=0,
            candidates=[],
        )

    feat_map = await uow.track_features.get_scoring_features_batch(all_ids)

    raw: list[tuple[int, TransitionCandidate]] = []
    total = len(all_ids)
    for i, tid in enumerate(all_ids):
        to_feat = feat_map.get(tid)
        if to_feat is None:
            continue
        result = scorer.score(src_feat, to_feat)
        if result.hard_reject:
            continue
        if result.overall < min_score:
            continue
        raw.append(
            (
                tid,
                TransitionCandidate(
                    track_id=tid,
                    title="",
                    overall=float(result.overall),
                    bpm=to_feat.bpm,
                    key=to_feat.key_code,
                    energy=to_feat.energy_mean,
                    mood=to_feat.mood,
                    best_transition=result.best_transition.name if result.best_transition else None,
                ),
            )
        )
        if i % 50 == 0:
            await safe_report_progress(ctx, progress=i, total=total)

    raw.sort(key=lambda t: t[1].overall, reverse=True)
    limited_raw = raw[:top_k]

    candidate_ids = [tid for tid, _ in limited_raw]
    track_map = await uow.tracks.get_many(candidate_ids) if candidate_ids else {}
    candidates = [
        TransitionCandidate(
            track_id=tid,
            title=getattr(track_map.get(tid), "title", "") or "",
            overall=cand.overall,
            bpm=cand.bpm,
            key=cand.key,
            energy=cand.energy,
            mood=cand.mood,
            best_transition=cand.best_transition,
        )
        for tid, cand in limited_raw
    ]

    return TransitionCandidatesResult(
        from_track_id=track_id,
        total_analyzed=len(all_ids),
        candidates=candidates,
    )
