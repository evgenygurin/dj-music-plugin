"""Storage backend factory for FastMCP caching and persistence.

Supports three backends:
- memory: In-memory (default, dev-friendly, no persistence)
- file: FileTreeStore (single-server, persists across restarts)
- redis: RedisStore (distributed, multi-server)

Configure via DJ_STORAGE_BACKEND env var.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from key_value.aio.stores.memory import MemoryStore

if TYPE_CHECKING:
    from key_value.aio.base import KeyValueStore

from dj_music.core.config import settings


def create_storage_backend() -> KeyValueStore:
    """Create storage backend based on settings.storage_backend.

    Returns:
        KeyValueStore instance (MemoryStore, FileTreeStore, or RedisStore)

    Raises:
        ValueError: If storage_backend is invalid or required dependency missing
    """
    backend = settings.storage_backend.lower()

    if backend == "memory":
        return MemoryStore()

    elif backend == "file":
        try:
            from key_value.aio.stores.filetree import (
                FileTreeStore,
                FileTreeV1CollectionSanitizationStrategy,
                FileTreeV1KeySanitizationStrategy,
            )
        except ImportError as e:
            raise ImportError("FileTreeStore requires py-key-value-aio. Run: uv sync") from e

        storage_dir = Path(settings.storage_file_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)

        return FileTreeStore(
            data_directory=storage_dir,
            key_sanitization_strategy=FileTreeV1KeySanitizationStrategy(storage_dir),
            collection_sanitization_strategy=FileTreeV1CollectionSanitizationStrategy(storage_dir),
        )

    elif backend == "redis":
        try:
            from key_value.aio.stores.redis import RedisStore
        except ImportError as e:
            raise ImportError(
                "RedisStore requires py-key-value-aio[redis]. Run: uv sync --extra redis"
            ) from e

        return RedisStore(
            host=settings.storage_redis_host,
            port=settings.storage_redis_port,
            password=settings.storage_redis_password or None,
            db=settings.storage_redis_db,
        )

    else:
        raise ValueError(f"Unknown storage_backend: {backend}. Valid options: memory, file, redis")


def create_transition_cache_backend() -> KeyValueStore:
    """Create dedicated storage for transition score cache.

    Uses same backend as general storage but with namespace separation
    when using Redis (via PrefixCollectionsWrapper).
    """
    base_store = create_storage_backend()

    # If Redis, add namespace prefix for transition cache
    if settings.storage_backend.lower() == "redis":
        try:
            from key_value.aio.wrappers.prefix_collections import PrefixCollectionsWrapper
        except ImportError:
            # Fallback: use base store without prefix
            return base_store

        return PrefixCollectionsWrapper(
            key_value=base_store,
            prefix="transition-cache",
        )

    return base_store
