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
