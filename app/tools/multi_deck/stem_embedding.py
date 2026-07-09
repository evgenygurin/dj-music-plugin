"""MCP tool: stem_embedding_search."""

from __future__ import annotations

from typing import Any

import numpy as np
from fastmcp.dependencies import Depends
from fastmcp.tools import tool

from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow


@tool(name="stem_embedding_search", annotations={"readOnlyHint": True, "idempotentHint": True})
async def stem_embedding_search(
    track_id: int,
    stem_name: str = "bass",
    embedding_type: str = "timbral",
    limit: int = 10,
    uow: UnitOfWork = Depends(get_uow),
) -> list[dict[str, Any]]:
    """Find similar stems using pgvector ANN search.

    Args:
        track_id: Source track to find similar stems to.
        stem_name: Which stem to match (drums/bass/vocals/other/original).
        embedding_type: Embedding type (timbral/harmonic/rhythmic/energy/full).
        limit: Max results.
    """
    emb_row = await uow.track_embeddings.get_for_type(track_id, stem_name, embedding_type)
    if emb_row is None:
        return []

    query = np.array(emb_row.embedding, dtype=np.float32)
    rows = await uow.track_embeddings.search_similar(
        query, embedding_type=embedding_type, stem_name=stem_name, limit=limit, exclude_ids=[track_id]
    )
    return [{"track_id": int(row[0]), "stem_name": stem_name, "similarity": round(row[1], 4)} for row in rows]
