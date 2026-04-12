"""Tests for platform metadata models (Task 15-16)."""

import pytest
from sqlalchemy.exc import IntegrityError

from dj_music.models.platform import (
    BeatportMetadata,
    SoundcloudMetadata,
    SpotifyAlbumMetadata,
    SpotifyArtistMetadata,
    SpotifyAudioFeatures,
    SpotifyMetadata,
    SpotifyPlaylistMetadata,
    YandexMetadata,
)
from dj_music.models.track import Track


async def _make_track(db, title: str = "Test Track") -> Track:
    """Helper: create and flush a Track, return it with id assigned."""
    t = Track(title=title)
    db.add(t)
    await db.flush()
    return t


# --- YandexMetadata ---


async def test_yandex_metadata_create(db):  # type: ignore[no-untyped-def]
    track = await _make_track(db)
    ym = YandexMetadata(
        track_id=track.id,
        yandex_track_id="12345",
        album_id="a1",
        album_title="Test Album",
        album_type="single",
        album_genre="techno",
        album_year=2024,
        label="Test Label",
        release_date="2024-01-15",
        duration_ms=360000,
        cover_uri="https://example.com/cover.jpg",
        explicit=False,
        extra='{"foo": "bar"}',
    )
    db.add(ym)
    await db.flush()
    assert ym.id is not None
    assert ym.track_id == track.id
    assert ym.yandex_track_id == "12345"
    assert ym.album_year == 2024
    assert ym.created_at is not None
    assert ym.updated_at is not None


async def test_yandex_metadata_unique_per_track(db):  # type: ignore[no-untyped-def]
    track = await _make_track(db)
    db.add(YandexMetadata(track_id=track.id, yandex_track_id="111"))
    await db.flush()
    db.add(YandexMetadata(track_id=track.id, yandex_track_id="222"))
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_yandex_metadata_nullable_fields(db):  # type: ignore[no-untyped-def]
    track = await _make_track(db)
    ym = YandexMetadata(track_id=track.id, yandex_track_id="999")
    db.add(ym)
    await db.flush()
    assert ym.album_id is None
    assert ym.label is None
    assert ym.explicit is None


# --- SpotifyMetadata ---


async def test_spotify_metadata_create(db):  # type: ignore[no-untyped-def]
    track = await _make_track(db)
    sm = SpotifyMetadata(
        track_id=track.id,
        spotify_track_id="sp_abc",
        album_id="sp_album_1",
        explicit=True,
        popularity=85,
        duration_ms=240000,
        preview_url="https://p.scdn.co/preview",
        release_date="2024-06-01",
        extra='{"isrc": "USRC123"}',
    )
    db.add(sm)
    await db.flush()
    assert sm.id is not None
    assert sm.spotify_track_id == "sp_abc"
    assert sm.popularity == 85
    assert sm.created_at is not None


async def test_spotify_metadata_unique_per_track(db):  # type: ignore[no-untyped-def]
    track = await _make_track(db)
    db.add(SpotifyMetadata(track_id=track.id, spotify_track_id="sp1"))
    await db.flush()
    db.add(SpotifyMetadata(track_id=track.id, spotify_track_id="sp2"))
    with pytest.raises(IntegrityError):
        await db.flush()


# --- Spotify sub-models ---


async def test_spotify_album_metadata_create(db):  # type: ignore[no-untyped-def]
    album = SpotifyAlbumMetadata(
        spotify_album_id="alb_001",
        title="Night Drive",
        album_type="album",
        total_tracks=12,
        release_date="2023-03-10",
        image_url="https://i.scdn.co/image/abc",
        label="Drumcode",
    )
    db.add(album)
    await db.flush()
    assert album.id is not None
    assert album.spotify_album_id == "alb_001"


async def test_spotify_album_metadata_unique_id(db):  # type: ignore[no-untyped-def]
    db.add(SpotifyAlbumMetadata(spotify_album_id="dup_album"))
    await db.flush()
    db.add(SpotifyAlbumMetadata(spotify_album_id="dup_album"))
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_spotify_artist_metadata_create(db):  # type: ignore[no-untyped-def]
    artist = SpotifyArtistMetadata(
        spotify_artist_id="art_001",
        name="Adam Beyer",
        genres='["techno", "industrial techno"]',
        popularity=72,
        image_url="https://i.scdn.co/image/artist",
    )
    db.add(artist)
    await db.flush()
    assert artist.id is not None
    assert artist.name == "Adam Beyer"


async def test_spotify_playlist_metadata_create(db):  # type: ignore[no-untyped-def]
    pl = SpotifyPlaylistMetadata(
        spotify_playlist_id="pl_001",
        name="Techno Bunker",
        description="Dark techno vibes",
        owner_id="user123",
        total_tracks=50,
        image_url="https://mosaic.scdn.co/img",
    )
    db.add(pl)
    await db.flush()
    assert pl.id is not None
    assert pl.name == "Techno Bunker"


async def test_spotify_audio_features_create(db):  # type: ignore[no-untyped-def]
    track = await _make_track(db)
    feat = SpotifyAudioFeatures(
        track_id=track.id,
        spotify_track_id="sp_feat_1",
        danceability=0.72,
        energy=0.89,
        key=5,
        loudness=-6.2,
        mode=1,
        speechiness=0.04,
        acousticness=0.01,
        instrumentalness=0.85,
        liveness=0.12,
        valence=0.35,
        tempo=132.5,
        duration_ms=420000,
        time_signature=4,
    )
    db.add(feat)
    await db.flush()
    assert feat.id is not None
    assert feat.energy == 0.89
    assert feat.tempo == 132.5


async def test_spotify_audio_features_unique_per_track(db):  # type: ignore[no-untyped-def]
    track = await _make_track(db)
    db.add(SpotifyAudioFeatures(track_id=track.id, spotify_track_id="sp1"))
    await db.flush()
    db.add(SpotifyAudioFeatures(track_id=track.id, spotify_track_id="sp2"))
    with pytest.raises(IntegrityError):
        await db.flush()


# --- BeatportMetadata & SoundcloudMetadata ---


async def test_beatport_metadata_create(db):  # type: ignore[no-untyped-def]
    track = await _make_track(db)
    bp = BeatportMetadata(
        track_id=track.id,
        beatport_track_id="bp_123",
        bpm=134.0,
        key="Gm",
        length="6:42",
        label="Drumcode",
        genre="Techno",
        subgenre="Peak Time",
    )
    db.add(bp)
    await db.flush()
    assert bp.id is not None
    assert bp.bpm == 134.0


async def test_soundcloud_metadata_create(db):  # type: ignore[no-untyped-def]
    track = await _make_track(db)
    sc = SoundcloudMetadata(
        track_id=track.id,
        soundcloud_track_id="sc_456",
        playback_count=15000,
        favoritings_count=320,
        reposts_count=45,
        comment_count=12,
        downloadable=True,
        streamable=True,
        permalink_url="https://soundcloud.com/artist/track",
        artwork_url="https://i1.sndcdn.com/artworks-abc",
        duration_ms=390000,
        genre="Techno",
        tag_list="techno dark industrial",
        description="A dark techno banger",
        license="all-rights-reserved",
        created_at_sc="2024-01-20T12:00:00Z",
    )
    db.add(sc)
    await db.flush()
    assert sc.id is not None
    assert sc.playback_count == 15000
    assert sc.downloadable is True
