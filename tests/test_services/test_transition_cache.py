"""Tests for TransitionScoreCache service."""

import pytest
from key_value.aio.stores.memory import MemoryStore

from app.services.transition_cache import CachedTransitionEntry, TransitionScoreCache


@pytest.fixture
async def cache() -> TransitionScoreCache:
    """Create cache with in-memory storage."""
    store = MemoryStore()
    return TransitionScoreCache(storage=store, ttl=3600)


@pytest.fixture
def sample_score() -> CachedTransitionEntry:
    """Sample transition score for testing."""
    return CachedTransitionEntry(
        track_id_a=1,
        track_id_b=2,
        bpm_score=0.95,
        harmonic_score=0.85,
        energy_score=0.75,
        spectral_score=0.80,
        groove_score=0.70,
        overall_score=0.81,
    )


@pytest.mark.asyncio
async def test_cache_miss(cache: TransitionScoreCache) -> None:
    """Test cache miss returns None."""
    result = await cache.get(1, 2)
    assert result is None


@pytest.mark.asyncio
async def test_cache_hit(cache: TransitionScoreCache, sample_score: CachedTransitionEntry) -> None:
    """Test cache hit returns stored score."""
    await cache.set(sample_score)
    result = await cache.get(1, 2)

    assert result is not None
    assert result.track_id_a == 1
    assert result.track_id_b == 2
    assert result.overall_score == 0.81


@pytest.mark.asyncio
async def test_cache_key_ordering(
    cache: TransitionScoreCache, sample_score: CachedTransitionEntry
) -> None:
    """Test cache key is symmetric (A→B same as B→A)."""
    await cache.set(sample_score)

    # Forward lookup
    result_forward = await cache.get(1, 2)
    assert result_forward is not None

    # Reverse lookup (should hit same cache entry)
    result_reverse = await cache.get(2, 1)
    assert result_reverse is not None
    assert result_reverse.overall_score == result_forward.overall_score


@pytest.mark.asyncio
async def test_invalidate_by_track_id(cache: TransitionScoreCache) -> None:
    """Test invalidating all scores involving a specific track."""
    # Cache 3 pairs: (1,2), (1,3), (4,5)
    await cache.set(
        CachedTransitionEntry(1, 2, 0.9, 0.8, 0.7, 0.6, 0.5, 0.7)
    )
    await cache.set(
        CachedTransitionEntry(1, 3, 0.9, 0.8, 0.7, 0.6, 0.5, 0.7)
    )
    await cache.set(
        CachedTransitionEntry(4, 5, 0.9, 0.8, 0.7, 0.6, 0.5, 0.7)
    )

    # Invalidate track 1
    await cache.invalidate(track_id=1)

    # (1,2) and (1,3) should be gone
    assert await cache.get(1, 2) is None
    assert await cache.get(1, 3) is None

    # (4,5) should still exist
    assert await cache.get(4, 5) is not None


@pytest.mark.asyncio
async def test_clear(cache: TransitionScoreCache) -> None:
    """Test clearing entire cache."""
    await cache.set(CachedTransitionEntry(1, 2, 0.9, 0.8, 0.7, 0.6, 0.5, 0.7))
    await cache.set(CachedTransitionEntry(3, 4, 0.9, 0.8, 0.7, 0.6, 0.5, 0.7))

    stats_before = await cache.stats()
    assert stats_before["size"] == 2

    await cache.clear()

    stats_after = await cache.stats()
    assert stats_after["size"] == 0

    assert await cache.get(1, 2) is None
    assert await cache.get(3, 4) is None


@pytest.mark.asyncio
async def test_stats(cache: TransitionScoreCache) -> None:
    """Test cache statistics."""
    stats_empty = await cache.stats()
    assert stats_empty["size"] == 0
    assert stats_empty["ttl"] == 3600

    await cache.set(CachedTransitionEntry(1, 2, 0.9, 0.8, 0.7, 0.6, 0.5, 0.7))
    await cache.set(CachedTransitionEntry(3, 4, 0.9, 0.8, 0.7, 0.6, 0.5, 0.7))

    stats_with_data = await cache.stats()
    assert stats_with_data["size"] == 2


@pytest.mark.asyncio
async def test_corrupted_cache_entry_returns_none(cache: TransitionScoreCache) -> None:
    """Test that corrupted cache entry returns None (cache miss)."""
    # Manually insert invalid dict (missing required fields)
    key = cache._make_key(1, 2)
    await cache.storage.put(
        collection=cache.collection,
        key=key,
        value={"invalid": "data"},  # Missing required CachedTransitionEntry fields
        ttl=cache.ttl,
    )

    result = await cache.get(1, 2)
    assert result is None  # Should treat as cache miss
