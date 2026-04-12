"""Tests for Track and related models (Task 8)."""

import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from dj_music.models.track import (
    Artist,
    Genre,
    Label,
    Release,
    Track,
    TrackArtist,
    TrackExternalId,
    TrackGenre,
    TrackLabel,
    TrackRelease,
)

# --- Entity creation ---


async def test_create_track(db):  # type: ignore[no-untyped-def]
    track = Track(title="Acid Rain")
    db.add(track)
    await db.flush()
    assert track.id is not None
    assert track.title == "Acid Rain"


async def test_create_artist(db):  # type: ignore[no-untyped-def]
    artist = Artist(name="Amelie Lens")
    db.add(artist)
    await db.flush()
    assert artist.id is not None
    assert artist.name == "Amelie Lens"


async def test_create_genre(db):  # type: ignore[no-untyped-def]
    genre = Genre(name="Techno")
    db.add(genre)
    await db.flush()
    assert genre.id is not None


async def test_create_label(db):  # type: ignore[no-untyped-def]
    label = Label(name="Drumcode")
    db.add(label)
    await db.flush()
    assert label.id is not None


async def test_create_release(db):  # type: ignore[no-untyped-def]
    release = Release(
        title="Character EP",
        release_date=datetime.date(2023, 6, 15),
        release_type="EP",
    )
    db.add(release)
    await db.flush()
    assert release.id is not None
    assert release.release_date == datetime.date(2023, 6, 15)


async def test_create_track_external_id(db):  # type: ignore[no-untyped-def]
    track = Track(title="Test Track")
    db.add(track)
    await db.flush()
    ext = TrackExternalId(track_id=track.id, platform="spotify", external_id="abc123")
    db.add(ext)
    await db.flush()
    assert ext.id is not None


# --- Default status ---


async def test_track_default_status(db):  # type: ignore[no-untyped-def]
    track = Track(title="Default Status")
    db.add(track)
    await db.flush()
    assert track.status == 0


# --- Genre hierarchy ---


async def test_genre_parent_child(db):  # type: ignore[no-untyped-def]
    parent = Genre(name="Techno")
    db.add(parent)
    await db.flush()

    child = Genre(name="Hard Techno", parent_id=parent.id)
    db.add(child)
    await db.flush()

    await db.refresh(parent, ["children"])
    await db.refresh(child, ["parent"])

    assert child.parent_id == parent.id
    assert child.parent is not None
    assert child.parent.name == "Techno"
    assert len(parent.children) == 1
    assert parent.children[0].name == "Hard Techno"


# --- Track-Artist association with role ---


async def test_track_artist_with_role(db):  # type: ignore[no-untyped-def]
    track = Track(title="Collaboration")
    artist = Artist(name="Charlotte de Witte")
    db.add_all([track, artist])
    await db.flush()

    ta = TrackArtist(track_id=track.id, artist_id=artist.id, role="primary")
    db.add(ta)
    await db.flush()

    await db.refresh(track, ["track_artists"])
    assert len(track.track_artists) == 1
    assert track.track_artists[0].role == "primary"
    assert track.track_artists[0].artist_id == artist.id


async def test_track_multiple_artist_roles(db):  # type: ignore[no-untyped-def]
    track = Track(title="Remix")
    artist = Artist(name="FJAAK")
    db.add_all([track, artist])
    await db.flush()

    ta1 = TrackArtist(track_id=track.id, artist_id=artist.id, role="primary")
    ta2 = TrackArtist(track_id=track.id, artist_id=artist.id, role="remixer")
    db.add_all([ta1, ta2])
    await db.flush()

    await db.refresh(track, ["track_artists"])
    assert len(track.track_artists) == 2
    roles = {ta.role for ta in track.track_artists}
    assert roles == {"primary", "remixer"}


# --- Timestamps ---


async def test_track_timestamps_auto_populated(db):  # type: ignore[no-untyped-def]
    track = Track(title="Timestamped")
    db.add(track)
    await db.flush()
    assert track.created_at is not None
    assert track.updated_at is not None


async def test_artist_timestamps(db):  # type: ignore[no-untyped-def]
    artist = Artist(name="Ben Klock")
    db.add(artist)
    await db.flush()
    assert artist.created_at is not None
    assert artist.updated_at is not None


# --- External ID unique constraint ---


async def test_external_id_unique_per_platform(db):  # type: ignore[no-untyped-def]
    track = Track(title="Unique Test")
    db.add(track)
    await db.flush()

    ext1 = TrackExternalId(track_id=track.id, platform="spotify", external_id="sp1")
    db.add(ext1)
    await db.flush()

    ext2 = TrackExternalId(track_id=track.id, platform="spotify", external_id="sp2")
    db.add(ext2)
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_external_id_different_platforms_ok(db):  # type: ignore[no-untyped-def]
    track = Track(title="Multi Platform")
    db.add(track)
    await db.flush()

    ext1 = TrackExternalId(track_id=track.id, platform="spotify", external_id="sp1")
    ext2 = TrackExternalId(track_id=track.id, platform="beatport", external_id="bp1")
    db.add_all([ext1, ext2])
    await db.flush()

    await db.refresh(track, ["external_ids"])
    assert len(track.external_ids) == 2


# --- Junction tables ---


async def test_track_genre_association(db):  # type: ignore[no-untyped-def]
    track = Track(title="Genre Test")
    genre = Genre(name="Acid")
    db.add_all([track, genre])
    await db.flush()

    tg = TrackGenre(track_id=track.id, genre_id=genre.id)
    db.add(tg)
    await db.flush()

    await db.refresh(track, ["track_genres"])
    assert len(track.track_genres) == 1


async def test_track_label_association(db):  # type: ignore[no-untyped-def]
    track = Track(title="Label Test")
    label = Label(name="Mord")
    db.add_all([track, label])
    await db.flush()

    tl = TrackLabel(track_id=track.id, label_id=label.id)
    db.add(tl)
    await db.flush()

    await db.refresh(track, ["track_labels"])
    assert len(track.track_labels) == 1


async def test_track_release_association(db):  # type: ignore[no-untyped-def]
    track = Track(title="Release Test")
    release = Release(title="Some EP")
    db.add_all([track, release])
    await db.flush()

    tr = TrackRelease(track_id=track.id, release_id=release.id, track_number=3)
    db.add(tr)
    await db.flush()

    await db.refresh(track, ["track_releases"])
    assert len(track.track_releases) == 1
    assert track.track_releases[0].track_number == 3


# --- Artist unique constraint ---


async def test_artist_name_unique(db):  # type: ignore[no-untyped-def]
    a1 = Artist(name="Dax J")
    db.add(a1)
    await db.flush()

    a2 = Artist(name="Dax J")
    db.add(a2)
    with pytest.raises(IntegrityError):
        await db.flush()


# --- Label unique constraint ---


async def test_label_name_unique(db):  # type: ignore[no-untyped-def]
    l1 = Label(name="Monnom Black")
    db.add(l1)
    await db.flush()

    l2 = Label(name="Monnom Black")
    db.add(l2)
    with pytest.raises(IntegrityError):
        await db.flush()
