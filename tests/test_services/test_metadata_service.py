"""Tests for MetadataService — normalize YM metadata into Artist/Genre/Label/Release."""

import pytest
from sqlalchemy import select

from dj_music.models.platform import YandexMetadata
from dj_music.models.track import (
    Artist,
    Genre,
    Label,
    Release,
    Track,
    TrackArtist,
    TrackGenre,
    TrackLabel,
    TrackRelease,
)
from dj_music.repositories.metadata import MetadataRepository
from dj_music.services.metadata_service import MetadataService


@pytest.fixture
def metadata_svc(db):
    """MetadataService with test DB session."""
    return MetadataService(MetadataRepository(db))


class _FakeYMTrack:
    """Minimal YMTrack-like object for testing."""

    def __init__(
        self,
        *,
        artists: list[dict] | None = None,
        albums: list[dict] | None = None,
    ):
        self.artists = artists or []
        self.albums = albums or []


async def _create_track(db, title="Amelie Lens - Exhale", duration_ms=360000) -> Track:
    """Helper: create a Track in DB."""
    track = Track(title=title, status=0, duration_ms=duration_ms)
    db.add(track)
    await db.flush()
    return track


async def _create_track_with_ym_meta(
    db,
    *,
    title="Amelie Lens - Exhale",
    album_genre="techno",
    label="Lenske",
    album_title="Exhale EP",
    album_year=2021,
    album_type="single",
) -> Track:
    """Helper: create Track + YandexMetadata."""
    track = await _create_track(db, title=title)
    meta = YandexMetadata(
        track_id=track.id,
        yandex_track_id=f"ym_{track.id}",
        album_genre=album_genre,
        label=label,
        album_title=album_title,
        album_year=album_year,
        album_type=album_type,
    )
    db.add(meta)
    await db.flush()
    return track


# ── Basic normalization from YMTrack ─────────────────


class TestNormalizeFromYMTrack:
    """Test normalization when YMTrack API object is provided."""

    async def test_artists_created_and_linked(self, db, metadata_svc):
        track = await _create_track(db)
        ym_track = _FakeYMTrack(
            artists=[{"name": "Amelie Lens"}, {"name": "Farrago"}],
        )

        result = await metadata_svc.normalize_track_metadata(track.id, ym_track=ym_track)

        assert result["artists"] == 2

        # Verify Artist records exist
        artists = (await db.execute(select(Artist))).scalars().all()
        names = {a.name for a in artists}
        assert "Amelie Lens" in names
        assert "Farrago" in names

        # Verify TrackArtist junctions
        junctions = (
            (await db.execute(select(TrackArtist).where(TrackArtist.track_id == track.id)))
            .scalars()
            .all()
        )
        assert len(junctions) == 2
        assert all(j.role == "primary" for j in junctions)

    async def test_genre_created_and_linked(self, db, metadata_svc):
        track = await _create_track(db)
        ym_track = _FakeYMTrack(
            albums=[{"genre": "techno", "title": "Some Album"}],
        )

        result = await metadata_svc.normalize_track_metadata(track.id, ym_track=ym_track)

        assert result["genres"] == 1

        genres = (await db.execute(select(Genre))).scalars().all()
        assert len(genres) == 1
        assert genres[0].name == "techno"

        junctions = (
            (await db.execute(select(TrackGenre).where(TrackGenre.track_id == track.id)))
            .scalars()
            .all()
        )
        assert len(junctions) == 1

    async def test_label_created_and_linked(self, db, metadata_svc):
        track = await _create_track(db)
        ym_track = _FakeYMTrack(
            albums=[{"labels": [{"name": "Drumcode"}], "title": "Test EP"}],
        )

        result = await metadata_svc.normalize_track_metadata(track.id, ym_track=ym_track)

        assert result["labels"] == 1

        labels = (await db.execute(select(Label))).scalars().all()
        assert len(labels) == 1
        assert labels[0].name == "Drumcode"

        junctions = (
            (await db.execute(select(TrackLabel).where(TrackLabel.track_id == track.id)))
            .scalars()
            .all()
        )
        assert len(junctions) == 1

    async def test_label_from_string_format(self, db, metadata_svc):
        """YM API sometimes returns labels as strings, not dicts."""
        track = await _create_track(db)
        ym_track = _FakeYMTrack(
            albums=[{"labels": ["Mord Records"], "title": "Test EP"}],
        )

        result = await metadata_svc.normalize_track_metadata(track.id, ym_track=ym_track)

        assert result["labels"] == 1
        labels = (await db.execute(select(Label))).scalars().all()
        assert labels[0].name == "Mord Records"

    async def test_release_created_and_linked(self, db, metadata_svc):
        track = await _create_track(db)
        ym_track = _FakeYMTrack(
            albums=[
                {
                    "title": "Exhale EP",
                    "year": 2021,
                    "type": "single",
                    "labels": [{"name": "Lenske"}],
                }
            ],
        )

        result = await metadata_svc.normalize_track_metadata(track.id, ym_track=ym_track)

        assert result["releases"] == 1

        releases = (await db.execute(select(Release))).scalars().all()
        assert len(releases) == 1
        assert releases[0].title == "Exhale EP"
        assert releases[0].release_type == "single"
        assert releases[0].release_date is not None
        assert releases[0].release_date.year == 2021
        # Label should be linked to release
        assert releases[0].label_id is not None

    async def test_full_normalization(self, db, metadata_svc):
        """Test all entities normalized in one call."""
        track = await _create_track(db, title="Amelie Lens, FJAAK - Blinding Light")
        ym_track = _FakeYMTrack(
            artists=[{"name": "Amelie Lens"}, {"name": "FJAAK"}],
            albums=[
                {
                    "title": "Blinding Light",
                    "year": 2023,
                    "type": "single",
                    "genre": "techno",
                    "labels": [{"name": "KNTXT"}],
                }
            ],
        )

        result = await metadata_svc.normalize_track_metadata(track.id, ym_track=ym_track)

        assert result["artists"] == 2
        assert result["genres"] == 1
        assert result["labels"] == 1
        assert result["releases"] == 1
        assert result["title_cleaned"] is True

        # Title should be cleaned
        track_db = (await db.execute(select(Track).where(Track.id == track.id))).scalar_one()
        assert track_db.title == "Blinding Light"

    async def test_title_not_cleaned_if_no_match(self, db, metadata_svc):
        """Title should not be cleaned if artist prefix doesn't match."""
        track = await _create_track(db, title="Some Completely Different Title")
        ym_track = _FakeYMTrack(artists=[{"name": "Amelie Lens"}])

        result = await metadata_svc.normalize_track_metadata(track.id, ym_track=ym_track)

        assert result["title_cleaned"] is False
        track_db = (await db.execute(select(Track).where(Track.id == track.id))).scalar_one()
        assert track_db.title == "Some Completely Different Title"


# ── Idempotency ──────────────────────────────────────


class TestIdempotency:
    """Test that running normalization twice doesn't duplicate entities."""

    async def test_idempotent_artists(self, db, metadata_svc):
        track = await _create_track(db)
        ym_track = _FakeYMTrack(artists=[{"name": "Amelie Lens"}])

        await metadata_svc.normalize_track_metadata(track.id, ym_track=ym_track)
        result2 = await metadata_svc.normalize_track_metadata(track.id, ym_track=ym_track)

        # Second call should find existing links
        assert result2["artists"] == 0

        artists = (await db.execute(select(Artist))).scalars().all()
        assert len(artists) == 1  # No duplicate

        junctions = (
            (await db.execute(select(TrackArtist).where(TrackArtist.track_id == track.id)))
            .scalars()
            .all()
        )
        assert len(junctions) == 1  # No duplicate junction

    async def test_idempotent_genre(self, db, metadata_svc):
        track = await _create_track(db)
        ym_track = _FakeYMTrack(albums=[{"genre": "techno", "title": "X"}])

        await metadata_svc.normalize_track_metadata(track.id, ym_track=ym_track)
        result2 = await metadata_svc.normalize_track_metadata(track.id, ym_track=ym_track)

        assert result2["genres"] == 0
        genres = (await db.execute(select(Genre))).scalars().all()
        assert len(genres) == 1

    async def test_shared_artist_across_tracks(self, db, metadata_svc):
        """Two tracks with the same artist should share the Artist record."""
        track1 = await _create_track(db, title="Track 1")
        track2 = await _create_track(db, title="Track 2")
        ym_track1 = _FakeYMTrack(artists=[{"name": "Amelie Lens"}])
        ym_track2 = _FakeYMTrack(artists=[{"name": "Amelie Lens"}])

        await metadata_svc.normalize_track_metadata(track1.id, ym_track=ym_track1)
        await metadata_svc.normalize_track_metadata(track2.id, ym_track=ym_track2)

        artists = (await db.execute(select(Artist))).scalars().all()
        assert len(artists) == 1  # Shared

        junctions = (await db.execute(select(TrackArtist))).scalars().all()
        assert len(junctions) == 2  # One per track

    async def test_shared_label_across_tracks(self, db, metadata_svc):
        track1 = await _create_track(db, title="Track 1")
        track2 = await _create_track(db, title="Track 2")
        ym1 = _FakeYMTrack(albums=[{"labels": [{"name": "Drumcode"}], "title": "EP1"}])
        ym2 = _FakeYMTrack(albums=[{"labels": [{"name": "Drumcode"}], "title": "EP2"}])

        await metadata_svc.normalize_track_metadata(track1.id, ym_track=ym1)
        await metadata_svc.normalize_track_metadata(track2.id, ym_track=ym2)

        labels = (await db.execute(select(Label))).scalars().all()
        assert len(labels) == 1  # Shared

    async def test_shared_release_across_tracks(self, db, metadata_svc):
        """Two tracks from the same album should share the Release record."""
        track1 = await _create_track(db, title="Track 1")
        track2 = await _create_track(db, title="Track 2")
        album = {"title": "Exhale EP", "year": 2021, "type": "single"}
        ym1 = _FakeYMTrack(albums=[album])
        ym2 = _FakeYMTrack(albums=[album])

        await metadata_svc.normalize_track_metadata(track1.id, ym_track=ym1)
        await metadata_svc.normalize_track_metadata(track2.id, ym_track=ym2)

        releases = (await db.execute(select(Release))).scalars().all()
        assert len(releases) == 1  # Shared

        junctions = (await db.execute(select(TrackRelease))).scalars().all()
        assert len(junctions) == 2  # One per track


# ── Fallback to YandexMetadata ───────────────────────


class TestFallbackToYandexMetadata:
    """Test normalization when no YMTrack is provided — falls back to DB metadata."""

    async def test_genre_from_ym_metadata(self, db, metadata_svc):
        track = await _create_track_with_ym_meta(db, album_genre="electronic")

        result = await metadata_svc.normalize_track_metadata(track.id)

        assert result["genres"] == 1
        genres = (await db.execute(select(Genre))).scalars().all()
        assert genres[0].name == "electronic"

    async def test_label_from_ym_metadata(self, db, metadata_svc):
        track = await _create_track_with_ym_meta(db, label="Drumcode")

        result = await metadata_svc.normalize_track_metadata(track.id)

        assert result["labels"] == 1
        labels = (await db.execute(select(Label))).scalars().all()
        assert labels[0].name == "Drumcode"

    async def test_release_from_ym_metadata(self, db, metadata_svc):
        track = await _create_track_with_ym_meta(
            db, album_title="Exhale EP", album_year=2021, album_type="single"
        )

        result = await metadata_svc.normalize_track_metadata(track.id)

        assert result["releases"] == 1
        releases = (await db.execute(select(Release))).scalars().all()
        assert releases[0].title == "Exhale EP"

    async def test_artists_from_track_title(self, db, metadata_svc):
        """When no YMTrack provided, artists should be parsed from track title."""
        track = await _create_track_with_ym_meta(db, title="Amelie Lens, FJAAK - Blinding Light")

        result = await metadata_svc.normalize_track_metadata(track.id)

        assert result["artists"] == 2
        artists = (await db.execute(select(Artist))).scalars().all()
        names = {a.name for a in artists}
        assert "Amelie Lens" in names
        assert "FJAAK" in names

    async def test_no_ym_metadata_returns_zeros(self, db, metadata_svc):
        """Track without YandexMetadata should return zero counts."""
        track = await _create_track(db)

        result = await metadata_svc.normalize_track_metadata(track.id)

        assert result["artists"] == 0
        assert result["genres"] == 0
        assert result["labels"] == 0
        assert result["releases"] == 0


# ── Edge cases ───────────────────────────────────────


class TestEdgeCases:
    """Edge cases and graceful handling of missing data."""

    async def test_empty_artist_name_skipped(self, db, metadata_svc):
        track = await _create_track(db)
        ym_track = _FakeYMTrack(artists=[{"name": ""}, {"name": "  "}, {"name": "Valid"}])

        result = await metadata_svc.normalize_track_metadata(track.id, ym_track=ym_track)

        assert result["artists"] == 1
        artists = (await db.execute(select(Artist))).scalars().all()
        assert len(artists) == 1
        assert artists[0].name == "Valid"

    async def test_no_genre_no_label_no_album(self, db, metadata_svc):
        track = await _create_track(db)
        ym_track = _FakeYMTrack(artists=[{"name": "Test Artist"}], albums=[])

        result = await metadata_svc.normalize_track_metadata(track.id, ym_track=ym_track)

        assert result["genres"] == 0
        assert result["labels"] == 0
        assert result["releases"] == 0

    async def test_album_without_title_skipped(self, db, metadata_svc):
        track = await _create_track(db)
        ym_track = _FakeYMTrack(albums=[{"genre": "techno"}])  # no title

        result = await metadata_svc.normalize_track_metadata(track.id, ym_track=ym_track)

        # Genre should still be linked
        assert result["genres"] == 1
        # But no release (no album title)
        assert result["releases"] == 0

    async def test_release_label_updated_on_second_pass(self, db, metadata_svc):
        """If release was created without label, second pass should update it."""
        track1 = await _create_track(db, title="Track 1")
        track2 = await _create_track(db, title="Track 2")

        # First: album without label
        ym1 = _FakeYMTrack(albums=[{"title": "Album X", "year": 2023}])
        await metadata_svc.normalize_track_metadata(track1.id, ym_track=ym1)

        release = (await db.execute(select(Release))).scalar_one()
        assert release.label_id is None

        # Second: same album with label
        ym2 = _FakeYMTrack(
            albums=[{"title": "Album X", "year": 2023, "labels": [{"name": "New Label"}]}]
        )
        await metadata_svc.normalize_track_metadata(track2.id, ym_track=ym2)

        releases = (await db.execute(select(Release))).scalars().all()
        assert len(releases) == 1  # Same release
        assert releases[0].label_id is not None

    async def test_missing_year_in_album(self, db, metadata_svc):
        """Album without year should still create a release."""
        track = await _create_track(db)
        ym_track = _FakeYMTrack(albums=[{"title": "Mystery EP"}])

        result = await metadata_svc.normalize_track_metadata(track.id, ym_track=ym_track)

        assert result["releases"] == 1
        release = (await db.execute(select(Release))).scalar_one()
        assert release.title == "Mystery EP"
        assert release.release_date is None


# ── Playlist normalization ───────────────────────────


class TestNormalizePlaylist:
    """Test batch normalization for an entire playlist."""

    async def test_normalize_playlist(self, db, metadata_svc):
        from dj_music.models.playlist import Playlist, PlaylistItem

        # Create tracks with YM metadata
        track1 = await _create_track_with_ym_meta(
            db,
            title="Artist A - Track 1",
            album_genre="techno",
            label="Label A",
            album_title="EP 1",
            album_year=2021,
        )
        track2 = await _create_track_with_ym_meta(
            db,
            title="Artist B - Track 2",
            album_genre="house",
            label="Label B",
            album_title="EP 2",
            album_year=2022,
        )

        # Create playlist with both tracks
        playlist = Playlist(name="Test Playlist")
        db.add(playlist)
        await db.flush()

        db.add(PlaylistItem(playlist_id=playlist.id, track_id=track1.id, sort_index=0))
        db.add(PlaylistItem(playlist_id=playlist.id, track_id=track2.id, sort_index=1))
        await db.flush()

        result = await metadata_svc.normalize_playlist(playlist.id)

        assert result["tracks_processed"] == 2
        assert result["artists_linked"] == 2  # One artist per track (from title)
        assert result["genres_linked"] == 2
        assert result["labels_linked"] == 2
        assert result["releases_linked"] == 2
