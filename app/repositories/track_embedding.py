from __future__ import annotations

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track_embedding import TrackEmbedding


class TrackEmbeddingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self, track_id: int, stem_name: str, embedding_type: str, embedding: np.ndarray
    ) -> TrackEmbedding:
        row = TrackEmbedding(
            track_id=track_id,
            stem_name=stem_name,
            embedding_type=embedding_type,
            embedding=embedding.tolist(),
        )
        await self._session.merge(row)
        await self._session.flush()
        return row

    async def search_similar(
        self,
        query_vector: np.ndarray,
        embedding_type: str = "full",
        stem_name: str = "original",
        limit: int = 20,
        exclude_ids: list[int] | None = None,
    ) -> list[tuple[int, float]]:
        vector_str = f"[{','.join(str(v) for v in query_vector)}]"
        sql = text("""
            SELECT t.id, 1 - (e.embedding <=> :query) AS similarity
            FROM track_embeddings e
            JOIN tracks t ON t.id = e.track_id
            WHERE e.embedding_type = :etype
              AND e.stem_name = :stem
            ORDER BY e.embedding <=> :query
            LIMIT :lim
        """)
        params = {"query": vector_str, "etype": embedding_type, "stem": stem_name, "lim": limit}
        result = await self._session.execute(sql, params)
        return [(row.id, row.similarity) for row in result.fetchall()]
