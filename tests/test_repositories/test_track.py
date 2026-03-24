"""Tests for TrackRepository — search and filtering."""

import pytest

from app.models.track import Track
from app.repositories.track import TrackRepository


@pytest.fixture
def track_repo(db):
    return TrackRepository(db)


async def test_search_by_text(track_repo, db):
    db.add(Track(title="Aphex Twin - Xtal"))
    db.add(Track(title="Autechre - Gantz Graf"))
    db.add(Track(title="Aphex Twin - Windowlicker"))
    await db.flush()

    results = await track_repo.search_by_text("Aphex")
    assert len(results) == 2
    assert all("Aphex" in t.title for t in results)


async def test_search_case_insensitive(track_repo, db):
    db.add(Track(title="BICEP - Glue"))
    await db.flush()

    results = await track_repo.search_by_text("bicep")
    assert len(results) == 1


async def test_search_no_results(track_repo, db):
    db.add(Track(title="Some Track"))
    await db.flush()

    results = await track_repo.search_by_text("nonexistent")
    assert len(results) == 0


async def test_search_limit(track_repo, db):
    for i in range(10):
        db.add(Track(title=f"Test Track {i}"))
    await db.flush()

    results = await track_repo.search_by_text("Test", limit=3)
    assert len(results) == 3
