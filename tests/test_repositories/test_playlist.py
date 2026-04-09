"""Tests for PlaylistRepository."""

import pytest

from app.db.models.playlist import Playlist, PlaylistItem
from app.db.models.track import Track
from app.db.repositories.playlist import PlaylistRepository


@pytest.fixture
def playlist_repo(db):
    return PlaylistRepository(db)


async def test_get_with_items(playlist_repo, db):
    pl = Playlist(name="Test PL")
    t1 = Track(title="Track A")
    t2 = Track(title="Track B")
    db.add_all([pl, t1, t2])
    await db.flush()

    db.add(PlaylistItem(playlist_id=pl.id, track_id=t1.id, sort_index=0))
    db.add(PlaylistItem(playlist_id=pl.id, track_id=t2.id, sort_index=1))
    await db.flush()

    result = await playlist_repo.get_with_items(pl.id)
    assert result is not None
    assert len(result.items) == 2


async def test_add_track(playlist_repo, db):
    pl = Playlist(name="PL")
    t = Track(title="T")
    db.add_all([pl, t])
    await db.flush()

    item = await playlist_repo.add_track(pl.id, t.id, position=0)
    assert item.sort_index == 0
    assert item.track_id == t.id


async def test_remove_track(playlist_repo, db):
    pl = Playlist(name="PL")
    t = Track(title="T")
    db.add_all([pl, t])
    await db.flush()

    db.add(PlaylistItem(playlist_id=pl.id, track_id=t.id, sort_index=0))
    await db.flush()

    removed = await playlist_repo.remove_track(pl.id, position=0)
    assert removed is True


async def test_get_track_ids(playlist_repo, db):
    """get_track_ids returns ordered track IDs for a playlist."""
    pl = Playlist(name="Test PL")
    t1 = Track(title="Track A")
    t2 = Track(title="Track B")
    t3 = Track(title="Track C")
    db.add_all([pl, t1, t2, t3])
    await db.flush()

    # Add tracks in non-sequential sort order
    db.add(PlaylistItem(playlist_id=pl.id, track_id=t3.id, sort_index=0))
    db.add(PlaylistItem(playlist_id=pl.id, track_id=t1.id, sort_index=1))
    db.add(PlaylistItem(playlist_id=pl.id, track_id=t2.id, sort_index=2))
    await db.flush()

    track_ids = await playlist_repo.get_track_ids(pl.id)
    assert track_ids == [t3.id, t1.id, t2.id]


async def test_get_track_ids_empty(playlist_repo, db):
    """get_track_ids returns empty list for playlist with no tracks."""
    pl = Playlist(name="Empty PL")
    db.add(pl)
    await db.flush()

    track_ids = await playlist_repo.get_track_ids(pl.id)
    assert track_ids == []
