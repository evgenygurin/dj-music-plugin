"""Tests for TransitionCache — in-memory LRU cache with TTL."""

from __future__ import annotations

import time

from app.core.cache import TransitionCache


def test_cache_stores_and_retrieves_score() -> None:
    """Cache stores transition score and retrieves it."""
    cache = TransitionCache(max_size=100, ttl=60)

    cache.put(
        1,
        2,
        bpm_score=0.9,
        harmonic_score=0.8,
        energy_score=0.85,
        spectral_score=0.7,
        groove_score=0.75,
        overall_score=0.8,
    )

    score = cache.get(1, 2)
    assert score is not None
    assert score.track_id_a == 1
    assert score.track_id_b == 2
    assert score.overall_score == 0.8
    assert score.bpm_score == 0.9


def test_cache_normalizes_key_order() -> None:
    """Cache normalizes (a,b) and (b,a) to same key."""
    cache = TransitionCache()

    cache.put(
        2,
        1,
        bpm_score=0.9,
        harmonic_score=0.8,
        energy_score=0.85,
        spectral_score=0.7,
        groove_score=0.75,
        overall_score=0.8,
    )

    # Retrieve with IDs in opposite order
    score = cache.get(1, 2)
    assert score is not None
    assert score.overall_score == 0.8


def test_cache_returns_none_for_missing() -> None:
    """Cache returns None for missing entries."""
    cache = TransitionCache()
    assert cache.get(1, 2) is None


def test_cache_evicts_lru_when_full() -> None:
    """Cache evicts least recently used entry when at capacity."""
    cache = TransitionCache(max_size=2, ttl=60)

    # Fill cache
    cache.put(
        1,
        2,
        bpm_score=0.9,
        harmonic_score=0.8,
        energy_score=0.85,
        spectral_score=0.7,
        groove_score=0.75,
        overall_score=0.8,
    )
    cache.put(
        3,
        4,
        bpm_score=0.9,
        harmonic_score=0.8,
        energy_score=0.85,
        spectral_score=0.7,
        groove_score=0.75,
        overall_score=0.8,
    )

    # Access first entry to make it recent
    cache.get(1, 2)

    # Add third entry — should evict (3,4) since it's LRU
    cache.put(
        5,
        6,
        bpm_score=0.9,
        harmonic_score=0.8,
        energy_score=0.85,
        spectral_score=0.7,
        groove_score=0.75,
        overall_score=0.8,
    )

    assert cache.get(1, 2) is not None  # still present
    assert cache.get(3, 4) is None  # evicted
    assert cache.get(5, 6) is not None  # newly added


def test_cache_expires_old_entries() -> None:
    """Cache returns None for entries older than TTL."""
    cache = TransitionCache(max_size=100, ttl=0.1)  # 100ms TTL

    cache.put(
        1,
        2,
        bpm_score=0.9,
        harmonic_score=0.8,
        energy_score=0.85,
        spectral_score=0.7,
        groove_score=0.75,
        overall_score=0.8,
    )

    # Immediate retrieval works
    assert cache.get(1, 2) is not None

    # Wait for expiry
    time.sleep(0.15)

    # Should return None (expired)
    assert cache.get(1, 2) is None


def test_cache_invalidate_track() -> None:
    """Cache invalidates all transitions involving a track."""
    cache = TransitionCache()

    cache.put(
        1,
        2,
        bpm_score=0.9,
        harmonic_score=0.8,
        energy_score=0.85,
        spectral_score=0.7,
        groove_score=0.75,
        overall_score=0.8,
    )
    cache.put(
        1,
        3,
        bpm_score=0.9,
        harmonic_score=0.8,
        energy_score=0.85,
        spectral_score=0.7,
        groove_score=0.75,
        overall_score=0.8,
    )
    cache.put(
        4,
        5,
        bpm_score=0.9,
        harmonic_score=0.8,
        energy_score=0.85,
        spectral_score=0.7,
        groove_score=0.75,
        overall_score=0.8,
    )

    # Invalidate all transitions involving track 1
    count = cache.invalidate_track(1)
    assert count == 2  # (1,2) and (1,3)

    assert cache.get(1, 2) is None
    assert cache.get(1, 3) is None
    assert cache.get(4, 5) is not None  # unaffected


def test_cache_clear() -> None:
    """Cache clear removes all entries."""
    cache = TransitionCache()

    cache.put(
        1,
        2,
        bpm_score=0.9,
        harmonic_score=0.8,
        energy_score=0.85,
        spectral_score=0.7,
        groove_score=0.75,
        overall_score=0.8,
    )
    cache.put(
        3,
        4,
        bpm_score=0.9,
        harmonic_score=0.8,
        energy_score=0.85,
        spectral_score=0.7,
        groove_score=0.75,
        overall_score=0.8,
    )

    cache.clear()

    assert cache.get(1, 2) is None
    assert cache.get(3, 4) is None
    assert cache.stats()["size"] == 0


def test_cache_stats() -> None:
    """Cache stats returns size, max_size, ttl, oldest_age."""
    cache = TransitionCache(max_size=100, ttl=3600)

    stats = cache.stats()
    assert stats["size"] == 0
    assert stats["max_size"] == 100
    assert stats["ttl"] == 3600
    assert stats["oldest_age_seconds"] is None

    cache.put(
        1,
        2,
        bpm_score=0.9,
        harmonic_score=0.8,
        energy_score=0.85,
        spectral_score=0.7,
        groove_score=0.75,
        overall_score=0.8,
    )

    stats = cache.stats()
    assert stats["size"] == 1
    assert isinstance(stats["oldest_age_seconds"], float)
    assert stats["oldest_age_seconds"] >= 0
