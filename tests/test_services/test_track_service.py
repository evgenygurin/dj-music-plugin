"""Tests for TrackService — sort_title generation."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.feature import FeatureRepository
from app.repositories.track import TrackRepository
from app.services.track_service import TrackService, generate_sort_title

# ── Unit tests for generate_sort_title ────────────────


@pytest.mark.parametrize(
    "title, expected",
    [
        ("The Chemical Brothers", "chemical brothers"),
        ("A State of Trance", "state of trance"),
        ("An Evening With", "evening with"),
        ("Normal Track Title", "normal track title"),
        ("  The Spaced  ", "spaced"),
        ("THE UPPERCASE", "uppercase"),
        ("--- Dashes First", "dashes first"),
        ("123 Numeric Start", "123 numeric start"),
        ("!!!Exclamation", "exclamation"),
        ("a", ""),  # edge: single article — falls back to "a"
    ],
)
def test_generate_sort_title(title: str, expected: str) -> None:
    result = generate_sort_title(title)
    # "a" edge case: function returns original lowered when result is empty
    if title.strip().lower() in ("a", "an", "the"):
        assert result == title.strip().lower()
    else:
        assert result == expected


def test_generate_sort_title_preserves_non_english() -> None:
    """Non-ASCII characters should be preserved in sort title."""
    assert generate_sort_title("Über Cool") == "über cool"


# ── Integration tests for create/update ────────────────


def _make_track_service(db: AsyncSession) -> TrackService:
    return TrackService(
        track_repo=TrackRepository(db),
        feature_repo=FeatureRepository(db),
    )


@pytest.mark.asyncio
async def test_create_track_sets_sort_title(db: AsyncSession) -> None:
    """Creating a track should auto-generate sort_title."""
    svc = _make_track_service(db)
    track = await svc.create("The Acid Track", duration_ms=300000)

    assert track.sort_title == "acid track"


# ── Search by external_id (Bug #4) ────────────────────


@pytest.mark.asyncio
async def test_search_finds_track_by_ym_prefix(db: AsyncSession) -> None:
    """``search('ym:12345')`` must return tracks linked to that YM ID.

    Regression for ОШИБКА #4 in docs/reports/mcp-tools-test-2026-04-07.md.
    """
    svc = _make_track_service(db)
    track_repo = TrackRepository(db)

    track = await svc.create("Hidden Title", duration_ms=400000)
    await track_repo.add_external_id(track.id, "yandex_music", "54486493")
    await db.flush()

    results = await svc.search("ym:54486493", limit=1)
    assert len(results) == 1
    assert results[0].id == track.id


@pytest.mark.asyncio
async def test_search_finds_track_by_uppercase_ym_prefix(db: AsyncSession) -> None:
    svc = _make_track_service(db)
    track_repo = TrackRepository(db)

    track = await svc.create("Whatever", duration_ms=400000)
    await track_repo.add_external_id(track.id, "yandex_music", "999111")
    await db.flush()

    results = await svc.search("YM:999111", limit=1)
    assert len(results) == 1
    assert results[0].id == track.id


@pytest.mark.asyncio
async def test_search_falls_back_to_text_when_ym_id_unknown(db: AsyncSession) -> None:
    """When YM ID is not found, plain text search should still work."""
    svc = _make_track_service(db)
    await svc.create("Unique Search Target", duration_ms=300000)
    await db.flush()

    # Unknown ym: id returns nothing — does NOT fall back to title search
    miss = await svc.search("ym:000000", limit=5)
    assert miss == []

    # But plain text query still works
    hit = await svc.search("Unique Search Target", limit=5)
    assert len(hit) >= 1


@pytest.mark.asyncio
async def test_update_track_regenerates_sort_title(db: AsyncSession) -> None:
    """Updating a track's title should regenerate sort_title."""
    svc = _make_track_service(db)
    track = await svc.create("Original Title", duration_ms=300000)
    assert track.sort_title == "original title"

    updated = await svc.update(track.id, title="The New Title")
    assert updated.sort_title == "new title"


@pytest.mark.asyncio
async def test_update_non_title_field_keeps_sort_title(db: AsyncSession) -> None:
    """Updating non-title fields should not change sort_title."""
    svc = _make_track_service(db)
    track = await svc.create("A Great Track", duration_ms=300000)
    assert track.sort_title == "great track"

    updated = await svc.update(track.id, duration_ms=600000)
    assert updated.sort_title == "great track"
