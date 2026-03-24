"""Pydantic response models for Yandex Music API."""

from __future__ import annotations

from pydantic import BaseModel


class YMTrack(BaseModel):
    """Track from YM API."""

    id: str
    title: str
    duration_ms: int | None = None
    artists: list[dict[str, object]] = []
    albums: list[dict[str, object]] = []
    cover_uri: str | None = None
    explicit: bool = False


class YMAlbum(BaseModel):
    """Album from YM API."""

    id: str
    title: str
    track_count: int | None = None
    artists: list[dict[str, object]] = []
    year: int | None = None
    genre: str | None = None


class YMArtist(BaseModel):
    """Artist from YM API."""

    id: str
    name: str


class YMPlaylist(BaseModel):
    """Playlist from YM API."""

    kind: int
    owner_id: str | None = None
    title: str
    track_count: int | None = None
    visibility: str | None = None
    revision: int | None = None


class YMSearchResults(BaseModel):
    """Aggregated search results from YM API."""

    tracks: list[YMTrack] = []
    albums: list[YMAlbum] = []
    artists: list[YMArtist] = []
    playlists: list[YMPlaylist] = []
