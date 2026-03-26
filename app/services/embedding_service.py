"""Embedding service — store, retrieve, and compare track vector embeddings.

Supports MFCC-based embeddings (13-dim) and extensible to other types.
Uses numpy for cosine similarity computation.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

import numpy as np

from app.core.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    from app.models.audio import Embedding
    from app.repositories.embedding import EmbeddingRepository


class EmbeddingService:
    """Store and retrieve vector embeddings for tracks."""

    def __init__(self, repo: EmbeddingRepository) -> None:
        self._repo = repo

    async def store_embedding(
        self,
        track_id: int,
        embedding_type: str,
        vector: list[float],
        model_name: str | None = None,
    ) -> Embedding:
        """Store a vector embedding for a track.

        If an embedding of the same type already exists for this track,
        it will be replaced (upsert).

        Args:
            track_id: Track to associate the embedding with.
            embedding_type: Type identifier (e.g. "mfcc", "spectral").
            vector: Float vector to store.
            model_name: Optional model identifier (for provenance).

        Returns:
            The persisted Embedding record.
        """
        if not vector:
            raise ValidationError("Embedding vector must not be empty", field="vector")

        vector_bytes = _serialize_vector(vector)
        dimensions = len(vector)

        return await self._repo.upsert_embedding(
            track_id=track_id,
            embedding_type=embedding_type,
            vector_data=vector_bytes,
            dimensions=dimensions,
        )

    async def get_embedding(
        self,
        track_id: int,
        embedding_type: str,
    ) -> list[float] | None:
        """Retrieve embedding vector for a track, or None if not stored."""
        record = await self._repo.get_embedding_record(track_id, embedding_type)
        if record is None:
            return None
        return _deserialize_vector(record.vector_data, record.dimensions)

    async def find_similar(
        self,
        track_id: int,
        embedding_type: str,
        limit: int = 10,
    ) -> list[tuple[int, float]]:
        """Find tracks most similar to the given track by cosine similarity.

        Args:
            track_id: Reference track.
            embedding_type: Type of embedding to compare.
            limit: Maximum number of results.

        Returns:
            List of (track_id, similarity_score) tuples, sorted by similarity descending.

        Raises:
            NotFoundError: If reference track has no embedding of this type.
        """
        ref_vector = await self.get_embedding(track_id, embedding_type)
        if ref_vector is None:
            raise NotFoundError("Embedding", f"track_id={track_id}, type={embedding_type}")

        # Load all embeddings of this type in one query
        all_embeddings = await self._repo.get_all_by_type(
            embedding_type, exclude_track_id=track_id
        )

        if not all_embeddings:
            return []

        # Compute cosine similarity against all candidates
        ref_arr = np.array(ref_vector, dtype=np.float64)
        ref_norm = np.linalg.norm(ref_arr)
        if ref_norm == 0:
            return []

        similarities: list[tuple[int, float]] = []
        for emb in all_embeddings:
            vec = _deserialize_vector(emb.vector_data, emb.dimensions)
            arr = np.array(vec, dtype=np.float64)
            norm = np.linalg.norm(arr)
            if norm == 0:
                continue
            cos_sim = float(np.dot(ref_arr, arr) / (ref_norm * norm))
            # Normalize from [-1, 1] to [0, 1]
            score = (cos_sim + 1.0) / 2.0
            similarities.append((emb.track_id, score))

        # Sort by similarity descending, take top N
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:limit]

    async def batch_store_from_mfcc(
        self,
        track_features: dict[int, list[float]],
    ) -> int:
        """Bulk-store MFCC vectors as embeddings.

        Args:
            track_features: Mapping of track_id -> mfcc_vector (13 floats).

        Returns:
            Number of embeddings stored.
        """
        count = 0
        for track_id, vector in track_features.items():
            if vector:
                await self.store_embedding(track_id, "mfcc", vector)
                count += 1
        return count


def _serialize_vector(vector: list[float]) -> bytes:
    """Serialize a float vector to bytes using struct (portable, compact)."""
    return struct.pack(f"<{len(vector)}d", *vector)


def _deserialize_vector(data: bytes, dimensions: int) -> list[float]:
    """Deserialize bytes back to a float vector."""
    return list(struct.unpack(f"<{dimensions}d", data))
