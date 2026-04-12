"""Tests for TrackRepository — search and filtering."""

import pytest

from dj_music.models.audio import TrackAudioFeaturesComputed
from dj_music.models.track import Track
from dj_music.repositories.track import TrackRepository


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


# ── Bug #6: filter_tracks sort_by direction ───────────


async def _seed_tracks_with_features(db, n: int = 5) -> list[int]:
    """Insert n tracks each with a feature row so filter joins succeed."""
    track_ids: list[int] = []
    for i in range(n):
        track = Track(title=f"Sort Test {i}")
        db.add(track)
        await db.flush()
        track_ids.append(track.id)
        db.add(
            TrackAudioFeaturesComputed(
                track_id=track.id,
                bpm=120.0 + i,
                energy_mean=0.5 + i * 0.05,
                analysis_level=3,
            )
        )
    await db.flush()
    return track_ids


async def test_filter_tracks_advanced_sort_by_id_desc(track_repo, db):
    """``sort_by='id_desc'`` must return tracks in descending id order.

    Regression for ОШИБКА #6 — direction suffix was silently ignored.
    """
    seeded = await _seed_tracks_with_features(db, n=5)

    page = await track_repo.filter_tracks_advanced(sort_by="id_desc", limit=10)
    ids = [t.id for t in page.items]
    assert len(ids) == len(seeded)
    assert ids == sorted(ids, reverse=True), f"Expected descending ids, got {ids}"


async def test_filter_tracks_advanced_sort_by_id_asc(track_repo, db):
    """``sort_by='id_asc'`` (and bare ``'id'``) must sort ascending."""
    seeded = await _seed_tracks_with_features(db, n=5)

    page = await track_repo.filter_tracks_advanced(sort_by="id_asc", limit=10)
    ids = [t.id for t in page.items]
    assert len(ids) == len(seeded)
    assert ids == sorted(ids)


async def test_filter_tracks_advanced_sort_by_bpm_desc(track_repo, db):
    """``sort_by='bpm_desc'`` should sort by BPM descending."""
    await _seed_tracks_with_features(db, n=5)

    page = await track_repo.filter_tracks_advanced(sort_by="bpm_desc", limit=10)
    # We can't read features off Track here without re-fetching; check ids.
    # Highest BPM (124) was added last → should appear first when desc.
    assert len(page.items) == 5
    # Last seeded track had highest BPM, so its id should be first
    assert page.items[0].id > page.items[-1].id
