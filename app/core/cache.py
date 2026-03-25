"""In-memory LRU cache for transition scores.

Transition scoring is expensive (5 components, full audio features).
Cache key: (track_id_a, track_id_b) ordered tuple.
Invalidation: when audio features of either track change.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class TransitionScore:
    """Cached transition score with all components."""

    track_id_a: int
    track_id_b: int
    bpm_score: float
    harmonic_score: float
    energy_score: float
    spectral_score: float
    groove_score: float
    overall_score: float
    cached_at: float


class TransitionCache:
    """LRU cache for transition scores with TTL and size limits."""

    def __init__(self, max_size: int = 10_000, ttl: int = 3600) -> None:
        """Initialize cache.

        Args:
            max_size: Maximum number of cached pairs
            ttl: Time-to-live in seconds
        """
        self._max_size = max_size
        self._ttl = ttl
        self._cache: dict[tuple[int, int], TransitionScore] = {}
        self._access_order: list[tuple[int, int]] = []

    def get(self, track_id_a: int, track_id_b: int) -> TransitionScore | None:
        """Get cached score for a track pair.

        Returns:
            Cached score if valid, None if expired or missing
        """
        # Normalize key (always smaller ID first)
        key = (
            (track_id_a, track_id_b)
            if track_id_a < track_id_b
            else (track_id_b, track_id_a)
        )

        score = self._cache.get(key)
        if score is None:
            return None

        # Check TTL
        age = time.monotonic() - score.cached_at
        if age > self._ttl:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            return None

        # Update LRU order
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

        return score

    def put(
        self,
        track_id_a: int,
        track_id_b: int,
        *,
        bpm_score: float,
        harmonic_score: float,
        energy_score: float,
        spectral_score: float,
        groove_score: float,
        overall_score: float,
    ) -> None:
        """Store transition score in cache.

        Args:
            track_id_a: First track ID
            track_id_b: Second track ID
            bpm_score: BPM compatibility score
            harmonic_score: Key compatibility score
            energy_score: Energy flow score
            spectral_score: Timbral similarity score
            groove_score: Rhythmic compatibility score
            overall_score: Weighted overall score
        """
        # Normalize key
        key = (
            (track_id_a, track_id_b)
            if track_id_a < track_id_b
            else (track_id_b, track_id_a)
        )

        # Evict oldest if at capacity
        if len(self._cache) >= self._max_size and key not in self._cache:
            if self._access_order:
                oldest = self._access_order.pop(0)
                del self._cache[oldest]

        # Store
        self._cache[key] = TransitionScore(
            track_id_a=track_id_a,
            track_id_b=track_id_b,
            bpm_score=bpm_score,
            harmonic_score=harmonic_score,
            energy_score=energy_score,
            spectral_score=spectral_score,
            groove_score=groove_score,
            overall_score=overall_score,
            cached_at=time.monotonic(),
        )

        # Update access order
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def invalidate_track(self, track_id: int) -> int:
        """Invalidate all cached transitions involving a track.

        Called when track's audio features change.

        Args:
            track_id: Track ID whose transitions to invalidate

        Returns:
            Number of invalidated entries
        """
        keys_to_remove = [
            key for key in self._cache if track_id in key
        ]

        for key in keys_to_remove:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)

        return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._access_order.clear()

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with size, max_size, ttl, oldest_age
        """
        oldest_age = None
        if self._cache:
            now = time.monotonic()
            oldest = min(score.cached_at for score in self._cache.values())
            oldest_age = now - oldest

        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl": self._ttl,
            "oldest_age_seconds": oldest_age,
        }
