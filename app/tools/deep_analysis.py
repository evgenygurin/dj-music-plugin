from __future__ import annotations

from typing import Any

import numpy as np
from fastmcp.dependencies import Depends
from fastmcp.tools import tool

from app.handlers.deep_analysis import handle_deep_analyze_track
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow


@tool(
    name="deep_analyze_track",
    annotations={"readOnlyHint": False, "idempotentHint": True},
)
async def deep_analyze_track(
    track_id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any]:
    return await handle_deep_analyze_track(track_id, uow)


@tool(
    name="deep_analyze_pool",
    annotations={"readOnlyHint": False},
)
async def deep_analyze_pool(
    track_ids: list[int],
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for tid in track_ids:
        results[str(tid)] = await handle_deep_analyze_track(tid, uow)
    return {"results": results, "total": len(track_ids)}


@tool(
    name="find_compatible_tracks",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def find_compatible_tracks(
    active_track_ids: list[int],
    embedding_type: str = "full",
    limit: int = 20,
    uow: UnitOfWork = Depends(get_uow),
) -> list[dict[str, Any]]:
    query = np.zeros(256, dtype=np.float32)
    count = 0
    for tid in active_track_ids:
        emb_row = await uow.track_embeddings.get_for_type(tid, "original", embedding_type)
        if emb_row is not None:
            query += np.array(emb_row.embedding, dtype=np.float32)
            count += 1

    if count > 0:
        query /= count

    rows = await uow.track_embeddings.search_similar(
        query, embedding_type=embedding_type, limit=limit, exclude_ids=active_track_ids
    )
    return [{"track_id": int(row[0]), "similarity": round(row[1], 4)} for row in rows]


@tool(
    name="get_cross_similarity",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def get_cross_similarity(
    track_a_id: int,
    track_b_id: int,
    stem_name: str = "original",
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any] | None:
    row = await uow.cross_similarity.get_for_pair(track_a_id, track_b_id, stem_name)
    if row is None:
        return None
    return {
        "track_a_id": row.track_a_id,
        "track_b_id": row.track_b_id,
        "best_match_offset_ms": row.best_match_offset_ms,
        "best_match_score": row.best_match_score,
        "alignment_path": row.alignment_path,
        "segment_matches": row.segment_matches,
    }
