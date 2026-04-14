"""MusicProvider — universal protocol for music platform clients.

Every platform adapter (YM, Soundcloud, Beatport, etc.) implements this
protocol. Services and tools depend on it, never on concrete clients.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from app.core.constants import Provider
from app.providers.models import (
    ProviderAlbum,
    ProviderPlaylist,
    ProviderSearchResults,
    ProviderTrack,
)


@runtime_checkable
class MusicProvider(Protocol):
    """Async interface every music platform client must satisfy."""

    @property
    def provider(self) -> Provider:
        """Which platform this client serves."""
        ...

    # ── Search ────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        *,
        search_type: str = "track",
        page: int = 0,
        page_size: int = 20,
    ) -> ProviderSearchResults: ...

    # ── Tracks ────────────────────────────────────────────────────────

    async def get_tracks(self, track_ids: list[str]) -> list[ProviderTrack]: ...

    async def get_similar(self, track_id: str) -> list[ProviderTrack]: ...

    async def get_download_info(self, track_id: str) -> list[dict[str, Any]]: ...

    async def download_track(self, track_id: str, dest_path: str | Path) -> int: ...

    # ── Albums ────────────────────────────────────────────────────────

    async def get_album(
        self,
        album_id: str,
        *,
        with_tracks: bool = False,
    ) -> ProviderAlbum: ...

    async def get_artist_tracks(
        self,
        artist_id: str,
        *,
        page: int = 0,
        page_size: int = 20,
    ) -> list[ProviderTrack]: ...

    # ── Playlists ─────────────────────────────────────────────────────

    async def get_playlist(self, playlist_id: str) -> ProviderPlaylist: ...

    async def get_playlist_tracks(self, playlist_id: str) -> list[ProviderTrack]: ...

    async def list_user_playlists(self) -> list[ProviderPlaylist]: ...

    async def create_playlist(
        self, title: str, *, visibility: str = "private"
    ) -> ProviderPlaylist: ...

    async def rename_playlist(self, playlist_id: str, name: str) -> bool: ...

    async def delete_playlist(self, playlist_id: str) -> bool: ...

    async def add_tracks_to_playlist(
        self,
        playlist_id: str,
        track_ids: list[str],
    ) -> bool: ...

    async def remove_tracks_from_playlist(
        self,
        playlist_id: str,
        track_ids: list[str],
    ) -> bool: ...

    # ── Likes / Library ───────────────────────────────────────────────

    async def get_liked_ids(self) -> set[str]: ...

    async def get_disliked_ids(self) -> set[str]: ...

    async def add_likes(self, track_ids: list[str]) -> bool: ...

    async def remove_likes(self, track_ids: list[str]) -> bool: ...

    # ── Audio streaming ───────────────────────────────────────────────

    async def get_stream_url(self, track_id: str) -> str:
        """Resolve a temporary direct URL for audio streaming."""
        ...

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def close(self) -> None: ...
