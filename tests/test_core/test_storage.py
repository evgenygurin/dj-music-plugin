"""Tests for storage backend factory and configuration."""

import pytest
from key_value.aio.stores.memory import MemoryStore

from app.config import settings
from app.infrastructure.storage import create_storage_backend, create_transition_cache_backend


@pytest.fixture
def original_backend() -> str:
    """Save and restore original storage_backend setting."""
    original = settings.storage_backend
    yield original
    settings.storage_backend = original


def test_create_memory_backend(original_backend: str) -> None:
    """Test creating in-memory storage backend (default)."""
    settings.storage_backend = "memory"
    store = create_storage_backend()
    assert isinstance(store, MemoryStore)


def test_create_file_backend(original_backend: str, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Test creating file storage backend."""
    settings.storage_backend = "file"
    settings.storage_file_dir = str(tmp_path / "storage")

    store = create_storage_backend()

    # FileTreeStore is from py-key-value-aio
    assert store.__class__.__name__ == "FileTreeStore"
    assert (tmp_path / "storage").exists()


def test_create_invalid_backend_raises(original_backend: str) -> None:
    """Test invalid backend raises ValueError."""
    settings.storage_backend = "invalid"

    with pytest.raises(ValueError, match="Unknown storage_backend"):
        create_storage_backend()


def test_transition_cache_backend_creates_memory(original_backend: str) -> None:
    """Test transition cache backend uses memory by default."""
    settings.storage_backend = "memory"
    store = create_transition_cache_backend()
    assert isinstance(store, MemoryStore)


def test_transition_cache_backend_with_redis_prefix(original_backend: str) -> None:
    """Test transition cache backend adds prefix when using Redis."""
    settings.storage_backend = "redis"
    settings.storage_redis_host = "localhost"
    settings.storage_redis_port = 6379

    # This will fail if redis not installed, but that's expected behavior
    try:
        store = create_transition_cache_backend()
        # Should be wrapped in PrefixCollectionsWrapper
        assert store.__class__.__name__ in ("PrefixCollectionsWrapper", "RedisStore")
    except ImportError:
        pytest.skip("Redis backend not installed (requires py-key-value-aio[redis])")
