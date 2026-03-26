"""Tests for ImportService — raw_provider_responses caching."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion import RawProviderResponse
from app.repositories.ingestion import IngestionRepository


# ── IngestionRepository unit tests ──────────────────


@pytest.mark.asyncio
async def test_cache_response_creates_record(db: AsyncSession) -> None:
    """cache_response should create a RawProviderResponse row."""
    repo = IngestionRepository(db)

    # First, we need a track
    from app.models.track import Track

    track = Track(title="Test Track", status=0)
    db.add(track)
    await db.flush()

    result = await repo.cache_response(
        track_id=track.id,
        provider_name="yandex_music",
        raw_data={"id": "12345", "title": "Test", "artists": []},
    )

    assert result is not None
    assert result.track_id == track.id
    assert result.raw_data is not None

    parsed = json.loads(result.raw_data)
    assert parsed["id"] == "12345"
    assert parsed["title"] == "Test"


@pytest.mark.asyncio
async def test_cache_response_upserts_existing(db: AsyncSession) -> None:
    """cache_response should update existing record instead of duplicating."""
    repo = IngestionRepository(db)

    from app.models.track import Track

    track = Track(title="Test Track 2", status=0)
    db.add(track)
    await db.flush()

    await repo.cache_response(track.id, "yandex_music", {"version": 1})
    await repo.cache_response(track.id, "yandex_music", {"version": 2})

    # Should have exactly 1 record
    stmt = select(RawProviderResponse).where(RawProviderResponse.track_id == track.id)
    result = await db.execute(stmt)
    records = list(result.scalars().all())
    assert len(records) == 1

    parsed = json.loads(records[0].raw_data)
    assert parsed["version"] == 2


@pytest.mark.asyncio
async def test_get_cached_response_returns_data(db: AsyncSession) -> None:
    """get_cached_response should return parsed JSON when cached."""
    repo = IngestionRepository(db)

    from app.models.track import Track

    track = Track(title="Cached Track", status=0)
    db.add(track)
    await db.flush()

    await repo.cache_response(track.id, "yandex_music", {"id": "999", "title": "Cached"})

    cached = await repo.get_cached_response(track.id, "yandex_music")
    assert cached is not None
    assert cached["id"] == "999"
    assert cached["title"] == "Cached"


@pytest.mark.asyncio
async def test_get_cached_response_returns_none_for_missing(db: AsyncSession) -> None:
    """get_cached_response should return None when no cache exists."""
    repo = IngestionRepository(db)

    from app.models.track import Track

    track = Track(title="Uncached Track", status=0)
    db.add(track)
    await db.flush()

    cached = await repo.get_cached_response(track.id, "yandex_music")
    assert cached is None


@pytest.mark.asyncio
async def test_ensure_provider_creates_if_missing(db: AsyncSession) -> None:
    """_ensure_provider_id should auto-create provider record."""
    repo = IngestionRepository(db)

    pid = await repo._ensure_provider_id("test_provider")
    assert pid > 0

    # Second call should return same id
    pid2 = await repo._ensure_provider_id("test_provider")
    assert pid2 == pid
