"""Tests for Playlist and PlaylistItem models."""

import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.playlist import Playlist, PlaylistItem
from app.models.track import Track


async def _make_track(db, title: str = "Test Track") -> Track:
    t = Track(title=title)
    db.add(t)
    await db.flush()
    return t


async def test_create_playlist(db):  # type: ignore[no-untyped-def]
    pl = Playlist(name="My Playlist")
    db.add(pl)
    await db.flush()
    assert pl.id is not None
    assert pl.name == "My Playlist"
    assert pl.source_of_truth == "local"
    assert pl.parent_id is None
    assert pl.source_app is None
    assert pl.platform_ids is None


async def test_playlist_hierarchy(db):  # type: ignore[no-untyped-def]
    parent = Playlist(name="Parent")
    db.add(parent)
    await db.flush()

    child = Playlist(name="Child", parent_id=parent.id)
    db.add(child)
    await db.flush()

    assert child.parent_id == parent.id


async def test_playlist_item_ordering(db):  # type: ignore[no-untyped-def]
    pl = Playlist(name="Ordered")
    db.add(pl)
    await db.flush()

    t1 = await _make_track(db, "Track A")
    t2 = await _make_track(db, "Track B")

    item1 = PlaylistItem(playlist_id=pl.id, track_id=t1.id, sort_index=0)
    item2 = PlaylistItem(playlist_id=pl.id, track_id=t2.id, sort_index=1)
    db.add_all([item1, item2])
    await db.flush()

    assert item1.sort_index == 0
    assert item2.sort_index == 1


async def test_playlist_item_unique_sort_index(db):  # type: ignore[no-untyped-def]
    pl = Playlist(name="Unique Sort")
    db.add(pl)
    await db.flush()

    t1 = await _make_track(db, "T1")
    t2 = await _make_track(db, "T2")

    db.add(PlaylistItem(playlist_id=pl.id, track_id=t1.id, sort_index=0))
    await db.flush()

    db.add(PlaylistItem(playlist_id=pl.id, track_id=t2.id, sort_index=0))
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_playlist_item_added_at(db):  # type: ignore[no-untyped-def]
    pl = Playlist(name="With Date")
    db.add(pl)
    await db.flush()

    t = await _make_track(db)
    now = datetime.datetime.now(tz=datetime.UTC)
    item = PlaylistItem(playlist_id=pl.id, track_id=t.id, sort_index=0, added_at=now)
    db.add(item)
    await db.flush()

    assert item.added_at == now


async def test_playlist_timestamps(db):  # type: ignore[no-untyped-def]
    pl = Playlist(name="Stamped")
    db.add(pl)
    await db.flush()
    assert pl.created_at is not None
    assert pl.updated_at is not None


async def test_playlist_with_platform_ids(db):  # type: ignore[no-untyped-def]
    pl = Playlist(
        name="YM Playlist",
        source_of_truth="yandex_music",
        platform_ids='{"yandex_music": "12345"}',
    )
    db.add(pl)
    await db.flush()
    assert pl.platform_ids is not None
    assert "12345" in pl.platform_ids
