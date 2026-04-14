"""Provider-agnostic data models.

Platform-specific clients map their native responses to these models
via their adapter. All services and tools work with these types,
never with platform-specific ones directly.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.core.constants import Provider


class ProviderArtist(BaseModel):
    id: str
    name: str
    provider: Provider


class ProviderTrack(BaseModel):
    id: str
    title: str
    artists: list[ProviderArtist] = []
    duration_ms: int | None = None
    album_id: str | None = None
    album_title: str | None = None
    album_genre: str | None = None
    cover_url: str | None = None
    explicit: bool = False
    provider: Provider

    @property
    def artist_names(self) -> str:
        return ", ".join(a.name for a in self.artists) or "Unknown"


class ProviderAlbum(BaseModel):
    id: str
    title: str
    track_count: int | None = None
    artists: list[ProviderArtist] = []
    year: int | None = None
    genre: str | None = None
    tracks: list[ProviderTrack] = []
    provider: Provider


class ProviderPlaylist(BaseModel):
    id: str
    owner_id: str | None = None
    title: str
    track_count: int | None = None
    provider: Provider


class ProviderSearchResults(BaseModel):
    tracks: list[ProviderTrack] = []
    albums: list[ProviderAlbum] = []
    artists: list[ProviderArtist] = []
    playlists: list[ProviderPlaylist] = []
