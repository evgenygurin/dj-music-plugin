"""Platform-specific metadata models (Task 15).

8 tables: yandex_metadata, spotify_metadata, spotify_album_metadata,
spotify_artist_metadata, spotify_playlist_metadata, spotify_audio_features,
beatport_metadata, soundcloud_metadata.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from dj_music.models.base import Base, TimestampMixin


class YandexMetadata(Base, TimestampMixin):
    """Yandex Music enrichment data for a track."""

    __tablename__ = "yandex_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), unique=True)
    yandex_track_id: Mapped[str] = mapped_column(String(100))
    album_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    album_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    album_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    album_genre: Mapped[str | None] = mapped_column(String(200), nullable=True)
    album_year: Mapped[int | None] = mapped_column(nullable=True)
    label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    release_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    cover_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    explicit: Mapped[bool | None] = mapped_column(nullable=True)
    extra: Mapped[str | None] = mapped_column(Text, nullable=True)


class SpotifyMetadata(Base, TimestampMixin):
    """Spotify enrichment data for a track."""

    __tablename__ = "spotify_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), unique=True)
    spotify_track_id: Mapped[str] = mapped_column(String(100))
    album_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    explicit: Mapped[bool | None] = mapped_column(nullable=True)
    popularity: Mapped[int | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    preview_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    release_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extra: Mapped[str | None] = mapped_column(Text, nullable=True)


class SpotifyAlbumMetadata(Base, TimestampMixin):
    """Spotify album metadata (standalone, not per-track)."""

    __tablename__ = "spotify_album_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    spotify_album_id: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    album_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_tracks: Mapped[int | None] = mapped_column(nullable=True)
    release_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    label: Mapped[str | None] = mapped_column(String(300), nullable=True)


class SpotifyArtistMetadata(Base, TimestampMixin):
    """Spotify artist metadata (standalone)."""

    __tablename__ = "spotify_artist_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    spotify_artist_id: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)
    popularity: Mapped[int | None] = mapped_column(nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class SpotifyPlaylistMetadata(Base, TimestampMixin):
    """Spotify playlist metadata (standalone)."""

    __tablename__ = "spotify_playlist_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    spotify_playlist_id: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_tracks: Mapped[int | None] = mapped_column(nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class SpotifyAudioFeatures(Base, TimestampMixin):
    """Spotify audio features for a track."""

    __tablename__ = "spotify_audio_features"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), unique=True)
    spotify_track_id: Mapped[str] = mapped_column(String(100))
    danceability: Mapped[float | None] = mapped_column(nullable=True)
    energy: Mapped[float | None] = mapped_column(nullable=True)
    key: Mapped[int | None] = mapped_column(nullable=True)
    loudness: Mapped[float | None] = mapped_column(nullable=True)
    mode: Mapped[int | None] = mapped_column(nullable=True)
    speechiness: Mapped[float | None] = mapped_column(nullable=True)
    acousticness: Mapped[float | None] = mapped_column(nullable=True)
    instrumentalness: Mapped[float | None] = mapped_column(nullable=True)
    liveness: Mapped[float | None] = mapped_column(nullable=True)
    valence: Mapped[float | None] = mapped_column(nullable=True)
    tempo: Mapped[float | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    time_signature: Mapped[int | None] = mapped_column(nullable=True)


class BeatportMetadata(Base, TimestampMixin):
    """Beatport enrichment data for a track."""

    __tablename__ = "beatport_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), unique=True)
    beatport_track_id: Mapped[str] = mapped_column(String(100))
    bpm: Mapped[float | None] = mapped_column(nullable=True)
    key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    length: Mapped[str | None] = mapped_column(String(20), nullable=True)
    label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    genre: Mapped[str | None] = mapped_column(String(200), nullable=True)
    subgenre: Mapped[str | None] = mapped_column(String(200), nullable=True)
    release_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    preview_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    extra: Mapped[str | None] = mapped_column(Text, nullable=True)


class SoundcloudMetadata(Base, TimestampMixin):
    """SoundCloud enrichment data for a track."""

    __tablename__ = "soundcloud_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), unique=True)
    soundcloud_track_id: Mapped[str] = mapped_column(String(100))
    playback_count: Mapped[int | None] = mapped_column(nullable=True)
    favoritings_count: Mapped[int | None] = mapped_column(nullable=True)
    reposts_count: Mapped[int | None] = mapped_column(nullable=True)
    comment_count: Mapped[int | None] = mapped_column(nullable=True)
    downloadable: Mapped[bool | None] = mapped_column(nullable=True)
    streamable: Mapped[bool | None] = mapped_column(nullable=True)
    permalink_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    artwork_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    genre: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tag_list: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at_sc: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extra: Mapped[str | None] = mapped_column(Text, nullable=True)
