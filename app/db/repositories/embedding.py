"""Embedding repository — DB operations for vector embeddings."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audio import Embedding
from app.db.repositories.base import BaseRepository


class EmbeddingRepository(BaseRepository[Embedding]):
    """Repository for :class:`Embedding` storage and retrieval."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Embedding)

    async def get_embedding_record(
        self,
        track_id: int,
        embedding_type: str,
    ) -> Embedding | None:
        """Fetch a single Embedding record by track_id and type."""
        stmt = select(Embedding).where(
            Embedding.track_id == track_id,
            Embedding.embedding_type == embedding_type,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_embedding(
        self,
        track_id: int,
        embedding_type: str,
        vector_data: bytes,
        dimensions: int,
    ) -> Embedding:
        """Create or update an embedding record. Returns the persisted record."""
        existing = await self.get_embedding_record(track_id, embedding_type)
        if existing is not None:
            existing.vector_data = vector_data
            existing.dimensions = dimensions
            await self.session.flush()
            return existing

        embedding = Embedding(
            track_id=track_id,
            embedding_type=embedding_type,
            dimensions=dimensions,
            vector_data=vector_data,
        )
        self.session.add(embedding)
        await self.session.flush()
        return embedding

    async def get_all_by_type(
        self,
        embedding_type: str,
        exclude_track_id: int | None = None,
    ) -> list[Embedding]:
        """Load all embeddings of a given type, optionally excluding one track."""
        stmt = select(Embedding).where(
            Embedding.embedding_type == embedding_type,
        )
        if exclude_track_id is not None:
            stmt = stmt.where(Embedding.track_id != exclude_track_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
