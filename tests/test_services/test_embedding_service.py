"""Tests for EmbeddingService — vector embedding storage and similarity."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.models.track import Track
from app.services.embedding_service import (
    EmbeddingService,
    _deserialize_vector,
    _serialize_vector,
)

# ── Fixtures ────────────────────────────────────────────


@pytest.fixture
async def svc(db: AsyncSession) -> EmbeddingService:
    return EmbeddingService(db)


async def _create_track(db: AsyncSession, track_id: int, title: str) -> Track:
    track = Track(id=track_id, title=title, status=0)
    db.add(track)
    await db.flush()
    return track


# ── Test: serialization helpers ─────────────────────────


def test_serialize_roundtrip() -> None:
    """Serialize then deserialize should give back the same vector."""
    vector = [1.0, 2.5, -3.14, 0.0, 42.0]
    data = _serialize_vector(vector)
    result = _deserialize_vector(data, len(vector))
    for a, b in zip(vector, result, strict=True):
        assert a == pytest.approx(b)


def test_serialize_empty_vector() -> None:
    """Empty vector should roundtrip correctly."""
    data = _serialize_vector([])
    result = _deserialize_vector(data, 0)
    assert result == []


def test_serialize_single_value() -> None:
    """Single float vector should work."""
    data = _serialize_vector([3.14])
    result = _deserialize_vector(data, 1)
    assert result[0] == pytest.approx(3.14)


# ── Test: store_embedding ───────────────────────────────


@pytest.mark.asyncio
async def test_store_embedding_basic(db: AsyncSession, svc: EmbeddingService) -> None:
    """Store and retrieve a basic embedding."""
    await _create_track(db, 1, "Test Track")

    emb = await svc.store_embedding(1, "mfcc", [1.0, 2.0, 3.0])

    assert emb.track_id == 1
    assert emb.embedding_type == "mfcc"
    assert emb.dimensions == 3


@pytest.mark.asyncio
async def test_store_embedding_upsert(db: AsyncSession, svc: EmbeddingService) -> None:
    """Storing same type for same track should update, not create duplicate."""
    await _create_track(db, 1, "Test Track")

    await svc.store_embedding(1, "mfcc", [1.0, 2.0, 3.0])
    await svc.store_embedding(1, "mfcc", [4.0, 5.0, 6.0])

    vector = await svc.get_embedding(1, "mfcc")
    assert vector is not None
    assert vector[0] == pytest.approx(4.0)


@pytest.mark.asyncio
async def test_store_embedding_different_types(db: AsyncSession, svc: EmbeddingService) -> None:
    """Different embedding types should coexist."""
    await _create_track(db, 1, "Test Track")

    await svc.store_embedding(1, "mfcc", [1.0, 2.0])
    await svc.store_embedding(1, "spectral", [3.0, 4.0, 5.0])

    mfcc = await svc.get_embedding(1, "mfcc")
    spectral = await svc.get_embedding(1, "spectral")

    assert mfcc is not None and len(mfcc) == 2
    assert spectral is not None and len(spectral) == 3


@pytest.mark.asyncio
async def test_store_embedding_empty_vector_raises(
    db: AsyncSession, svc: EmbeddingService
) -> None:
    """Empty vector should raise ValidationError."""
    await _create_track(db, 1, "Test Track")

    with pytest.raises(ValidationError, match="empty"):
        await svc.store_embedding(1, "mfcc", [])


# ── Test: get_embedding ─────────────────────────────────


@pytest.mark.asyncio
async def test_get_embedding_exists(db: AsyncSession, svc: EmbeddingService) -> None:
    """Should return the stored vector."""
    await _create_track(db, 1, "Test Track")
    await svc.store_embedding(1, "mfcc", [1.5, 2.5, 3.5])

    vector = await svc.get_embedding(1, "mfcc")

    assert vector is not None
    assert len(vector) == 3
    assert vector[0] == pytest.approx(1.5)
    assert vector[1] == pytest.approx(2.5)
    assert vector[2] == pytest.approx(3.5)


@pytest.mark.asyncio
async def test_get_embedding_not_exists(db: AsyncSession, svc: EmbeddingService) -> None:
    """Should return None for non-existing embedding."""
    result = await svc.get_embedding(9999, "mfcc")
    assert result is None


# ── Test: find_similar ──────────────────────────────────


@pytest.mark.asyncio
async def test_find_similar_basic(db: AsyncSession, svc: EmbeddingService) -> None:
    """Should find similar tracks by cosine similarity."""
    for i in range(1, 5):
        await _create_track(db, i, f"Track {i}")

    # Track 1: reference vector
    await svc.store_embedding(1, "mfcc", [1.0, 0.0, 0.0])
    # Track 2: identical direction → highest similarity
    await svc.store_embedding(2, "mfcc", [2.0, 0.0, 0.0])
    # Track 3: 45 degrees → medium similarity
    await svc.store_embedding(3, "mfcc", [1.0, 1.0, 0.0])
    # Track 4: opposite → lowest similarity
    await svc.store_embedding(4, "mfcc", [-1.0, 0.0, 0.0])

    results = await svc.find_similar(1, "mfcc", limit=10)

    assert len(results) == 3
    # Results should be sorted by similarity descending
    track_ids = [r[0] for r in results]
    assert track_ids[0] == 2  # identical direction
    assert track_ids[1] == 3  # 45 degrees
    assert track_ids[2] == 4  # opposite

    # Check scores are in [0, 1]
    for _, score in results:
        assert 0.0 <= score <= 1.0

    # Identical direction should have score = 1.0
    assert results[0][1] == pytest.approx(1.0)

    # Opposite direction should have score = 0.0
    assert results[2][1] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_find_similar_with_limit(db: AsyncSession, svc: EmbeddingService) -> None:
    """Limit should restrict results."""
    for i in range(1, 6):
        await _create_track(db, i, f"Track {i}")
        await svc.store_embedding(i, "mfcc", [float(i), 0.0])

    results = await svc.find_similar(1, "mfcc", limit=2)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_find_similar_no_embedding_raises(db: AsyncSession, svc: EmbeddingService) -> None:
    """Should raise NotFoundError if reference track has no embedding."""
    with pytest.raises(NotFoundError):
        await svc.find_similar(9999, "mfcc")


@pytest.mark.asyncio
async def test_find_similar_no_other_tracks(db: AsyncSession, svc: EmbeddingService) -> None:
    """Should return empty list if no other tracks have embeddings."""
    await _create_track(db, 1, "Solo Track")
    await svc.store_embedding(1, "mfcc", [1.0, 2.0])

    results = await svc.find_similar(1, "mfcc")
    assert results == []


@pytest.mark.asyncio
async def test_find_similar_orthogonal_vectors(db: AsyncSession, svc: EmbeddingService) -> None:
    """Orthogonal vectors should have similarity ~0.5 (cos=0, normalized to 0.5)."""
    await _create_track(db, 1, "Track A")
    await _create_track(db, 2, "Track B")

    await svc.store_embedding(1, "mfcc", [1.0, 0.0])
    await svc.store_embedding(2, "mfcc", [0.0, 1.0])

    results = await svc.find_similar(1, "mfcc")
    assert len(results) == 1
    assert results[0][1] == pytest.approx(0.5)


# ── Test: batch_store_from_mfcc ─────────────────────────


@pytest.mark.asyncio
async def test_batch_store_from_mfcc(db: AsyncSession, svc: EmbeddingService) -> None:
    """Batch store should create embeddings for all tracks."""
    for i in range(1, 4):
        await _create_track(db, i, f"Track {i}")

    mfcc_data = {
        1: [1.0, 2.0, 3.0],
        2: [4.0, 5.0, 6.0],
        3: [7.0, 8.0, 9.0],
    }

    count = await svc.batch_store_from_mfcc(mfcc_data)
    assert count == 3

    for track_id, expected in mfcc_data.items():
        vec = await svc.get_embedding(track_id, "mfcc")
        assert vec is not None
        for a, b in zip(vec, expected, strict=True):
            assert a == pytest.approx(b)


@pytest.mark.asyncio
async def test_batch_store_skips_empty(db: AsyncSession, svc: EmbeddingService) -> None:
    """Batch store should skip tracks with empty MFCC vectors."""
    await _create_track(db, 1, "Track 1")
    await _create_track(db, 2, "Track 2")

    count = await svc.batch_store_from_mfcc({1: [1.0, 2.0], 2: []})
    assert count == 1


# ── Test: 13-dim MFCC vector (realistic) ───────────────


@pytest.mark.asyncio
async def test_mfcc_13_dim_roundtrip(db: AsyncSession, svc: EmbeddingService) -> None:
    """13-dimensional MFCC vector (as used in the real pipeline)."""
    await _create_track(db, 1, "Track")

    mfcc = [-200.0, 50.0, 20.0, -10.0, 5.0, -3.0, 2.0, -1.5, 1.0, -0.5, 0.3, -0.2, 0.1]
    assert len(mfcc) == 13

    await svc.store_embedding(1, "mfcc", mfcc)
    result = await svc.get_embedding(1, "mfcc")

    assert result is not None
    assert len(result) == 13
    for a, b in zip(mfcc, result, strict=True):
        assert a == pytest.approx(b)
