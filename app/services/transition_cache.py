"""Transition score caching layer using FastMCP storage backends.

Provides async cache for computed transition scores between track pairs.
Supports multiple backends (memory, file, redis) via py-key-value-aio.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from key_value.aio.stores.base import BaseEnumerateKeysStore as KeyValueStore


@dataclass
class CachedTransitionEntry:
    """Cached transition score entry for KV-store backend.

    Wraps score components with track pair identifiers for cache storage.
    """

    track_id_a: int
    track_id_b: int
    bpm_score: float
    harmonic_score: float
    energy_score: float
    spectral_score: float
    groove_score: float
    overall_score: float


class TransitionScoreCache:
    """Cache for transition scores using pluggable storage backend.

    Args:
        storage: KeyValueStore backend (memory, file, redis)
        ttl: Time-to-live in seconds (default 3600)
        collection_name: Storage collection/namespace (default "transition_scores")
    """

    def __init__(
        self,
        storage: KeyValueStore,
        ttl: int = 3600,
        collection_name: str = "transition_scores",
    ) -> None:
        self.storage = storage
        self.ttl = ttl
        self.collection = collection_name

    def _make_key(self, track_id_a: int, track_id_b: int) -> str:
        """Create cache key from ordered track IDs."""
        # Always order IDs to ensure A→B and B→A hit same cache entry
        # (symmetric transitions in DJ context)
        ordered = tuple(sorted([track_id_a, track_id_b]))
        return f"{ordered[0]}:{ordered[1]}"

    async def get(self, track_id_a: int, track_id_b: int) -> CachedTransitionEntry | None:
        """Retrieve cached transition score.

        Returns:
            CachedTransitionEntry if cached, None if miss
        """
        key = self._make_key(track_id_a, track_id_b)
        value = await self.storage.get(collection=self.collection, key=key)

        if value is None:
            return None

        # Deserialize from dict (py-key-value-aio stores structured data)
        try:
            return CachedTransitionEntry(**value)
        except (TypeError, KeyError):
            # Invalid cache entry — return miss
            return None

    async def set(self, score: CachedTransitionEntry) -> None:
        """Store transition score in cache.

        Args:
            score: CachedTransitionEntry to cache
        """
        key = self._make_key(score.track_id_a, score.track_id_b)
        # py-key-value-aio stores structured data (dict), not JSON string
        value = asdict(score)
        await self.storage.put(
            collection=self.collection,
            key=key,
            value=value,
            ttl=self.ttl,
        )

    async def invalidate(self, track_id: int) -> None:
        """Invalidate all cached scores involving this track.

        Called when track's audio features change.

        Note: This is O(n) scan for memory/file backends. For production
        with redis, consider maintaining a secondary index of track→keys.
        """
        # List all keys in collection
        keys = await self.storage.keys(collection=self.collection)

        # Delete keys containing this track_id
        for key in keys:
            parts = key.split(":")
            if len(parts) == 2:
                try:
                    id_a, id_b = int(parts[0]), int(parts[1])
                    if track_id in (id_a, id_b):
                        await self.storage.delete(collection=self.collection, key=key)
                except ValueError:
                    # Invalid key format — skip
                    continue

    async def clear(self) -> None:
        """Clear all cached transition scores."""
        # Get all keys first, then delete them one by one
        # (destroy_collection makes collection unavailable for subsequent operations)
        keys = await self.storage.keys(collection=self.collection)
        for key in keys:
            await self.storage.delete(collection=self.collection, key=key)

    async def stats(self) -> dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary with cache size and (if supported) hit/miss counts
        """
        keys = await self.storage.keys(collection=self.collection)
        return {
            "size": len(keys),
            "ttl": self.ttl,
        }
