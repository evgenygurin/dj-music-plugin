"""Adapter: YandexMusicClient → MusicProvider protocol.

Translates YM-specific API (owner_id + kind playlists, revision-based
mutations, YM models) into the universal MusicProvider interface.

Playlist IDs are encoded as ``"owner_id:kind"`` strings. Methods that
mutate playlists re-fetch revision automatically.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.clients.ym.client import YandexMusicClient
from app.clients.ym.models import YMAlbum, YMArtist, YMPlaylist, YMTrack
from app.core.constants import Provider
from app.providers.models import (
    ProviderAlbum,
    ProviderArtist,
    ProviderPlaylist,
    ProviderSearchResults,
    ProviderTrack,
)

_log = logging.getLogger(__name__)

_PROVIDER = Provider.YANDEX_MUSIC


class YandexMusicAdapter:
    """Wraps :class:`YandexMusicClient` to satisfy :class:`MusicProvider`."""

    def __init__(self, client: YandexMusicClient) -> None:
        self._client = client

    @property
    def provider(self) -> Provider:
        return _PROVIDER

    @property
    def raw_client(self) -> YandexMusicClient:
        """Access the underlying YM client for platform-specific operations."""
        return self._client

    # ── Search ────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        *,
        search_type: str = "track",
        page: int = 0,
        page_size: int = 20,
    ) -> ProviderSearchResults:
        ym_result = await self._client.search(query, type=search_type, limit=page_size)
        return ProviderSearchResults(
            tracks=[_convert_track(t) for t in ym_result.tracks],
            albums=[_convert_album(a) for a in ym_result.albums],
            artists=[_convert_artist(a) for a in ym_result.artists],
            playlists=[_convert_playlist(p) for p in ym_result.playlists],
        )

    # ── Tracks ────────────────────────────────────────────────────────

    async def get_tracks(self, track_ids: list[str]) -> list[ProviderTrack]:
        ym_tracks = await self._client.get_tracks(track_ids)
        return [_convert_track(t) for t in ym_tracks]

    async def get_similar(self, track_id: str) -> list[ProviderTrack]:
        ym_tracks = await self._client.get_similar(track_id)
        return [_convert_track(t) for t in ym_tracks]

    async def get_download_info(self, track_id: str) -> list[dict[str, Any]]:
        return await self._client.get_download_info(track_id)

    async def download_track(self, track_id: str, dest_path: str | Path) -> int:
        return await self._client.download_track(track_id, str(dest_path))

    # ── Albums ────────────────────────────────────────────────────────

    async def get_album(
        self,
        album_id: str,
        *,
        with_tracks: bool = False,
    ) -> ProviderAlbum:
        ym_album = await self._client.get_album(album_id, with_tracks=with_tracks)
        return _convert_album(ym_album)

    async def get_artist_tracks(
        self,
        artist_id: str,
        *,
        page: int = 0,
        page_size: int = 20,
    ) -> list[ProviderTrack]:
        ym_tracks = await self._client.get_artist_tracks(artist_id, page=page)
        return [_convert_track(t) for t in ym_tracks]

    # ── Playlists ─────────────────────────────────────────────────────

    def _parse_playlist_id(self, playlist_id: str) -> tuple[str, int]:
        """Parse ``"owner_id:kind"`` → (owner_id, kind)."""
        owner, kind_str = playlist_id.split(":", 1)
        return owner, int(kind_str)

    def _make_playlist_id(self, owner_id: str | None, kind: int) -> str:
        return f"{owner_id or self._client._user_id}:{kind}"

    async def get_playlist(self, playlist_id: str) -> ProviderPlaylist:
        owner, kind = self._parse_playlist_id(playlist_id)
        ym_pl = await self._client.get_playlist(owner, kind)
        return _convert_playlist(ym_pl)

    async def get_playlist_tracks(self, playlist_id: str) -> list[ProviderTrack]:
        owner, kind = self._parse_playlist_id(playlist_id)
        ym_tracks = await self._client.get_playlist_tracks(owner, kind)
        return [_convert_track(t) for t in ym_tracks]

    async def list_user_playlists(self) -> list[ProviderPlaylist]:
        ym_playlists = await self._client.list_user_playlists()
        return [_convert_playlist(p) for p in ym_playlists]

    async def create_playlist(
        self, title: str, *, visibility: str = "private"
    ) -> ProviderPlaylist:
        ym_pl = await self._client.create_playlist(title, visibility=visibility)
        return _convert_playlist(ym_pl)

    async def rename_playlist(self, playlist_id: str, name: str) -> bool:
        _, kind = self._parse_playlist_id(playlist_id)
        return await self._client.rename_playlist(kind, name)

    async def delete_playlist(self, playlist_id: str) -> bool:
        _, kind = self._parse_playlist_id(playlist_id)
        return await self._client.delete_playlist(kind)

    async def add_tracks_to_playlist(
        self,
        playlist_id: str,
        track_ids: list[str],
    ) -> bool:
        owner, kind = self._parse_playlist_id(playlist_id)
        pl = await self._client.get_playlist(owner, kind)
        revision = pl.revision or 0
        resolved = await self._client.resolve_track_ids_with_albums(track_ids)
        await self._client.add_tracks_to_playlist(kind, resolved, revision)
        return True

    async def remove_tracks_from_playlist(
        self,
        playlist_id: str,
        track_ids: list[str],
    ) -> bool:
        owner, kind = self._parse_playlist_id(playlist_id)
        ym_tracks = await self._client.get_playlist_tracks(owner, kind)
        pl = await self._client.get_playlist(owner, kind)
        revision = pl.revision or 0

        ids_to_remove = set(track_ids)
        indices = [i for i, t in enumerate(ym_tracks) if t.id in ids_to_remove]
        if not indices:
            return True

        for from_idx in sorted(indices, reverse=True):
            await self._client.remove_tracks_from_playlist(kind, from_idx, from_idx + 1, revision)
            pl = await self._client.get_playlist(owner, kind)
            revision = pl.revision or 0
        return True

    # ── Likes / Library ───────────────────────────────────────────────

    async def get_liked_ids(self) -> set[str]:
        return await self._client.get_liked_ids()

    async def get_disliked_ids(self) -> set[str]:
        return await self._client.get_disliked_ids()

    async def add_likes(self, track_ids: list[str]) -> bool:
        return await self._client.add_likes(track_ids)

    async def remove_likes(self, track_ids: list[str]) -> bool:
        return await self._client.remove_likes(track_ids)

    # ── Audio streaming ───────────────────────────────────────────────

    async def get_stream_url(self, track_id: str) -> str:
        infos = await self._client.get_download_info(track_id)
        if not infos:
            from app.core.errors import APIError

            raise APIError(404, f"No download info for track {track_id}")
        best = infos[0]
        info_url = best.get("downloadInfoUrl", "")
        return await self._client._resolve_download_url(track_id, info_url)

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def close(self) -> None:
        await self._client.close()


# ── Converters: YM models → Provider models ──────────────────────────


def _extract_artist_name(raw: dict[str, object]) -> str:
    return str(raw.get("name", "Unknown"))


def _extract_artist_id(raw: dict[str, object]) -> str:
    return str(raw.get("id", ""))


def _convert_track(ym: YMTrack) -> ProviderTrack:
    albums = ym.albums or []
    first_album = albums[0] if albums else {}
    return ProviderTrack(
        id=ym.id,
        title=ym.title,
        artists=[
            ProviderArtist(
                id=_extract_artist_id(a),
                name=_extract_artist_name(a),
                provider=_PROVIDER,
            )
            for a in ym.artists
        ],
        duration_ms=ym.duration_ms,
        album_id=str(first_album.get("id", "")) if first_album else None,
        album_title=str(first_album.get("title", "")) if first_album else None,
        album_genre=str(first_album.get("genre", "")) if first_album else None,
        cover_url=f"https://{ym.cover_uri.replace('%%', '200x200')}" if ym.cover_uri else None,
        explicit=ym.explicit,
        provider=_PROVIDER,
    )


def _convert_artist(ym: YMArtist) -> ProviderArtist:
    return ProviderArtist(
        id=ym.id,
        name=ym.name,
        provider=_PROVIDER,
    )


def _convert_album(ym: YMAlbum) -> ProviderAlbum:
    return ProviderAlbum(
        id=ym.id,
        title=ym.title,
        track_count=ym.track_count,
        artists=[
            ProviderArtist(
                id=_extract_artist_id(a),
                name=_extract_artist_name(a),
                provider=_PROVIDER,
            )
            for a in ym.artists
        ],
        year=ym.year,
        genre=ym.genre,
        tracks=[_convert_track(t) for t in ym.tracks],
        provider=_PROVIDER,
    )


def _convert_playlist(ym: YMPlaylist) -> ProviderPlaylist:
    return ProviderPlaylist(
        id=f"{ym.owner_id or ''}:{ym.kind}",
        owner_id=ym.owner_id,
        title=ym.title,
        track_count=ym.track_count,
        provider=_PROVIDER,
    )
