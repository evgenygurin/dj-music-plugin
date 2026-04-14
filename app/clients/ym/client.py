"""Async HTTP client for Yandex Music API.

All methods are async and return typed Pydantic models.
Rate limiting is enforced via RateLimiter (token bucket + exponential backoff).

After every playlist modification, the caller MUST re-fetch the playlist
to get the updated revision and track indices.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import httpx

from app.clients.ym.models import (
    YMAlbum,
    YMArtist,
    YMPlaylist,
    YMSearchResults,
    YMTrack,
)
from app.clients.ym.rate_limiter import RateLimiter
from app.core.errors import APIError, AuthFailedError, RateLimitedError

_log = logging.getLogger(__name__)

# Sign salt for /tracks/{id}/download-info → MP3 URL signing.
# This is a public constant baked into the YM client implementation.
_DOWNLOAD_SIGN_SALT = "XGRlBW9FXlekgbPrRHuSiA"


class YandexMusicClient:
    """Async Yandex Music API client with rate limiting and retries."""

    def __init__(
        self,
        token: str,
        user_id: str,
        base_url: str,
        rate_limiter: RateLimiter,
    ) -> None:
        self._token = token
        self._user_id = user_id
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"OAuth {token}"},
            timeout=30.0,
        )
        self._rate_limiter = rate_limiter

    # ── Core request method ───────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make a rate-limited request with error handling and retries on 429."""
        await self._rate_limiter.acquire()

        for attempt in range(self._rate_limiter.max_retries + 1):
            response = await self._client.request(method, path, **kwargs)

            if response.status_code == 200:
                data: dict[str, Any] = response.json()
                return data
            elif response.status_code == 429:
                if attempt < self._rate_limiter.max_retries:
                    delay = self._rate_limiter.get_backoff_delay(attempt)
                    await asyncio.sleep(delay)
                    continue
                raise RateLimitedError(
                    retry_after=self._rate_limiter.get_backoff_delay(attempt),
                )
            elif response.status_code == 401:
                raise AuthFailedError()
            elif response.status_code == 403:
                # 403 is NOT always auth failure on YM — it's also
                # returned for region-locked / DMCA'd / unavailable tracks.
                # Classify as APIError so callers can handle per-track
                # without tearing down the whole pipeline.
                raise APIError(response.status_code, response.text)
            else:
                raise APIError(response.status_code, response.text)

        raise RateLimitedError()  # unreachable but satisfies type checker

    # ── Search ────────────────────────────────────────────

    async def search(
        self,
        query: str,
        type: str = "all",
        limit: int = 10,
    ) -> YMSearchResults:
        """Search tracks, albums, artists, playlists.

        Response structure: {"result": {"tracks": {"results": [...]}, ...}}
        When `type` is specified, only that section is populated.
        """
        # YM API uses singular type names (track, album, artist, playlist)
        type_map = {
            "tracks": "track",
            "albums": "album",
            "artists": "artist",
            "playlists": "playlist",
        }
        api_type = type_map.get(type, type)
        data = await self._request(
            "GET",
            "/search",
            params={"text": query, "type": api_type, "page": 0, "page-size": limit},
        )
        result = data.get("result", {})

        tracks_section = result.get("tracks", {})
        albums_section = result.get("albums", {})
        artists_section = result.get("artists", {})
        playlists_section = result.get("playlists", {})

        return YMSearchResults(
            tracks=[
                _parse_track(t)
                for t in (tracks_section.get("results", []) if tracks_section else [])
            ],
            albums=[
                _parse_album(a)
                for a in (albums_section.get("results", []) if albums_section else [])
            ],
            artists=[
                _parse_artist(a)
                for a in (artists_section.get("results", []) if artists_section else [])
            ],
            playlists=[
                _parse_playlist(p)
                for p in (playlists_section.get("results", []) if playlists_section else [])
            ],
        )

    # ── Tracks ────────────────────────────────────────────

    async def get_tracks(self, track_ids: list[str]) -> list[YMTrack]:
        """Fetch tracks by IDs (batch, up to 100)."""
        data = await self._request(
            "GET",
            "/tracks",
            params={"trackIds": ",".join(track_ids)},
        )
        raw_tracks: list[dict[str, Any]] = data.get("result", [])
        return [_parse_track(t) for t in raw_tracks]

    async def get_similar(self, track_id: str) -> list[YMTrack]:
        """Get similar tracks for a given track.

        4xx responses (endpoint blocked, no data) are downgraded to an
        empty list — callers cannot distinguish "no similar tracks" from
        "endpoint unavailable" anyway, and the consumer behavior is the
        same. 5xx and network errors keep their original :class:`APIError`.
        """
        try:
            data = await self._request("GET", f"/tracks/{track_id}/similar")
        except APIError as exc:
            if 400 <= exc.status_code < 500:
                _log.warning(
                    "ym.get_similar(%s) returned %s — degrading to empty list",
                    track_id,
                    exc.status_code,
                )
                return []
            raise

        similar = data.get("result", {}).get("similarTracks", [])
        return [_parse_track(t) for t in similar]

    # ── Download ──────────────────────────────────────────

    async def get_download_info(self, track_id: str) -> list[dict[str, Any]]:
        """Get download URLs and codecs for a track.

        Returns list of download options sorted by bitrate (highest first).
        Each has: codec, bitrate_in_kbps, src (download URL), gain, preview.
        """
        data = await self._request(
            "GET",
            f"/tracks/{track_id}/download-info",
        )
        infos: list[dict[str, Any]] = data.get("result", [])
        # Sort by bitrate descending
        return sorted(infos, key=lambda x: x.get("bitrateInKbps", 0), reverse=True)

    async def download_track(
        self,
        track_id: str,
        dest_path: str,
        prefer_bitrate: int = 320,
    ) -> int:
        """Download MP3 file for a track. Returns file size in bytes.

        Two-step process:
        1. GET /tracks/{id}/download-info → list of download options
        2. Pick best bitrate → GET download URL with sign + ts params
        """
        infos = await self.get_download_info(track_id)
        if not infos:
            raise APIError(404, f"No download info for track {track_id}")

        # Pick best matching bitrate (infos already sorted by bitrate desc)
        best = infos[0]
        for info in infos:
            if info.get("bitrateInKbps", 0) <= prefer_bitrate and info.get("codec") == "mp3":
                best = info
                break

        download_info_url = best.get("downloadInfoUrl")
        if not download_info_url:
            raise APIError(404, f"No downloadInfoUrl for track {track_id}")

        # Step 2a: fetch signed XML with host/path/ts/s parts
        download_url = await self._resolve_download_url(track_id, download_info_url)

        # Step 2b: stream the MP3 to disk
        return await self._stream_to_file(track_id, download_url, dest_path)

    async def _resolve_download_url(self, track_id: str, info_url: str) -> str:
        """Fetch the signed XML descriptor and build the final MP3 URL.

        Wraps HTTP and XML errors in :class:`APIError` so callers see a
        single, well-typed failure mode instead of leaking ``httpx`` /
        ``xml.etree`` exceptions.
        """
        await self._rate_limiter.acquire()
        try:
            resp = await self._client.get(
                info_url, headers={"Authorization": f"OAuth {self._token}"}
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise APIError(
                exc.response.status_code,
                f"Download info request failed for {track_id}: {exc.response.text}",
            ) from exc
        except httpx.RequestError as exc:
            raise APIError(500, f"Download info network error for {track_id}: {exc}") from exc

        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as exc:
            raise APIError(500, f"Invalid download info XML for track {track_id}: {exc}") from exc

        host = root.findtext("host")
        path = root.findtext("path")
        ts = root.findtext("ts")
        s = root.findtext("s")

        if not host or not path or not ts or not s:
            raise APIError(500, f"Incomplete download info XML for track {track_id}")

        sign = hashlib.md5(f"{_DOWNLOAD_SIGN_SALT}{path[1:]}{s}".encode()).hexdigest()
        return f"https://{host}/get-mp3/{sign}/{ts}{path}"

    async def _stream_to_file(self, track_id: str, download_url: str, dest_path: str) -> int:
        """Stream a download URL to disk. Returns bytes written."""
        await self._rate_limiter.acquire()
        try:
            async with self._client.stream("GET", download_url) as stream:
                stream.raise_for_status()
                dest = Path(dest_path)
                dest.parent.mkdir(parents=True, exist_ok=True)
                file_size = 0
                with dest.open("wb") as f:
                    async for chunk in stream.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
                        file_size += len(chunk)
        except httpx.HTTPStatusError as exc:
            raise APIError(
                exc.response.status_code,
                f"Download stream failed for {track_id}: {exc.response.text}",
            ) from exc
        except httpx.RequestError as exc:
            raise APIError(500, f"Download stream network error for {track_id}: {exc}") from exc

        return file_size

    # ── Albums ────────────────────────────────────────────

    async def get_album(
        self,
        album_id: str,
        with_tracks: bool = False,
    ) -> YMAlbum:
        """Fetch album info, optionally with tracks."""
        path = f"/albums/{album_id}"
        if with_tracks:
            path += "/with-tracks"
        try:
            data = await self._request("GET", path)
        except APIError as exc:
            # YM rejects out-of-range IDs (e.g. >9 digits) with HTTP 400
            # ``validate`` error instead of HTTP 404. Treat any 4xx for
            # a single-album lookup as "not found" so the tool layer can
            # raise a clean ``Album not found`` ToolError. 5xx / network
            # errors keep their original APIError.
            if 400 <= exc.status_code < 500:
                return _parse_album({})
            raise

        # YM API returns ``{"result": null}`` (or omits ``result``) when
        # the album does not exist — including for syntactically valid
        # but out-of-range numeric IDs. Coerce to an empty dict so
        # ``_parse_album`` produces an empty stub. The result may also
        # contain a top-level ``error`` field with the actual id but no
        # album metadata; treat that the same way.
        result = data.get("result")
        if not isinstance(result, dict) or "error" in result:
            result = {}
        return _parse_album(result)

    # ── Artists ───────────────────────────────────────────

    async def get_artist_tracks(
        self,
        artist_id: str,
        page: int = 0,
    ) -> list[YMTrack]:
        """Fetch paginated tracks by artist."""
        data = await self._request(
            "GET",
            f"/artists/{artist_id}/tracks",
            params={"page": page, "pageSize": 20},
        )
        raw_tracks: list[dict[str, Any]] = data.get("result", {}).get("tracks", [])
        return [_parse_track(t) for t in raw_tracks]

    # ── Playlists ─────────────────────────────────────────

    async def get_playlist(self, owner_id: str, kind: int) -> YMPlaylist:
        """Fetch a playlist by owner and kind."""
        data = await self._request(
            "GET",
            f"/users/{owner_id}/playlists/{kind}",
        )
        return _parse_playlist(data.get("result", {}))

    async def get_playlist_tracks(self, owner_id: str, kind: int) -> list[YMTrack]:
        """Fetch all tracks from a playlist with full metadata.

        YM API returns tracks as ``[{"id": N, "track": {...}, "timestamp": ...}]``.
        We parse the inner ``track`` object.
        """
        data = await self._request(
            "GET",
            f"/users/{owner_id}/playlists/{kind}",
        )
        result = data.get("result", {})
        raw_items: list[dict[str, Any]] = result.get("tracks", [])
        return [
            _parse_track(item["track"])
            for item in raw_items
            if isinstance(item, dict) and "track" in item
        ]

    async def resolve_track_ids_with_albums(self, track_ids: list[str]) -> list[str]:
        """Resolve bare track IDs to ``"trackId:albumId"`` format required by YM API.

        IDs that already contain ``:`` are returned as-is.
        IDs without album info are batch-fetched from YM API.
        """
        bare = [tid for tid in track_ids if ":" not in tid]

        album_map: dict[str, str] = {}
        batch_size = 100
        for start in range(0, len(bare), batch_size):
            batch = bare[start : start + batch_size]
            tracks = await self.get_tracks(batch)
            for t in tracks:
                albums = t.albums or []
                if albums:
                    album_id = (
                        str(albums[0].get("id", ""))
                        if isinstance(albums[0], dict)
                        else str(getattr(albums[0], "id", ""))
                    )
                    if album_id:
                        album_map[t.id] = album_id

        result: list[str] = []
        for tid in track_ids:
            if ":" in tid:
                result.append(tid)
            else:
                album_id = album_map.get(tid, "")
                result.append(f"{tid}:{album_id}" if album_id else tid)
        return result

    async def get_disliked_ids(self) -> set[str]:
        """Fetch user's disliked track IDs."""
        data = await self._request(
            "GET",
            f"/users/{self._user_id}/dislikes/tracks",
        )
        result = data.get("result", {})
        library = result.get("library", result)
        tracks_raw: list[dict[str, Any]] = library.get("tracks", [])
        return {str(t.get("id", "")) for t in tracks_raw if t.get("id")}

    async def list_user_playlists(self) -> list[YMPlaylist]:
        """List all playlists for the authenticated user."""
        data = await self._request(
            "GET",
            f"/users/{self._user_id}/playlists/list",
        )
        raw: list[dict[str, Any]] = data.get("result", [])
        return [_parse_playlist(p) for p in raw]

    async def create_playlist(
        self,
        name: str,
        visibility: str = "private",
    ) -> YMPlaylist:
        """Create a new playlist.

        After creation, re-fetch to get full metadata if needed.
        """
        data = await self._request(
            "POST",
            f"/users/{self._user_id}/playlists/create",
            data={"title": name, "visibility": visibility},
        )
        return _parse_playlist(data.get("result", {}))

    async def rename_playlist(self, kind: int, name: str) -> bool:
        """Rename a playlist. Returns True on success.

        After rename, re-fetch the playlist to get updated metadata.
        """
        await self._request(
            "POST",
            f"/users/{self._user_id}/playlists/{kind}/name",
            data={"value": name},
        )
        return True

    async def delete_playlist(self, kind: int) -> bool:
        """Delete a playlist. Returns True on success."""
        await self._request(
            "POST",
            f"/users/{self._user_id}/playlists/{kind}/delete",
        )
        return True

    async def add_tracks_to_playlist(
        self,
        kind: int,
        track_ids: list[str],
        revision: int,
    ) -> dict[str, Any]:
        """Add tracks to playlist using YM JSON diff format.

        Uses ``{"op": "insert", "at": 0, "tracks": [...]}`` diff.

        After modification, the caller MUST re-fetch the playlist
        to get the updated revision and track indices.
        """
        tracks_payload = []
        for tid in track_ids:
            if ":" in str(tid):
                track_id, album_id = str(tid).split(":", 1)
                tracks_payload.append({"id": track_id, "albumId": album_id})
            else:
                tracks_payload.append({"id": str(tid), "albumId": ""})
        diff = json.dumps(
            [{"op": "insert", "at": 0, "tracks": tracks_payload}],
        )
        data = await self._request(
            "POST",
            f"/users/{self._user_id}/playlists/{kind}/change-relative",
            data={"diff": diff, "revision": revision},
        )
        result: dict[str, Any] = data.get("result", {})
        return result

    async def remove_tracks_from_playlist(
        self,
        kind: int,
        from_idx: int,
        to_idx: int,
        revision: int,
    ) -> dict[str, Any]:
        """Remove tracks from playlist by index range.

        Uses ``{"op": "delete", "from": from_idx, "to": to_idx}`` diff.
        ``from`` is inclusive, ``to`` is exclusive.

        After modification, the caller MUST re-fetch the playlist
        to get the updated revision and track indices.
        """
        diff = json.dumps([{"op": "delete", "from": from_idx, "to": to_idx}])
        data = await self._request(
            "POST",
            f"/users/{self._user_id}/playlists/{kind}/change-relative",
            data={"diff": diff, "revision": revision},
        )
        result: dict[str, Any] = data.get("result", {})
        return result

    # ── Likes ─────────────────────────────────────────────

    async def get_liked_ids(self) -> set[str]:
        """Get IDs of all liked tracks for the authenticated user.

        Returns a ``set`` to mirror :meth:`get_disliked_ids` and to make
        membership checks O(1) at the call site (most consumers want to
        ask "is this track liked?", not iterate ordered).
        """
        data = await self._request(
            "GET",
            f"/users/{self._user_id}/likes/tracks",
        )
        library = data.get("result", {}).get("library", {})
        tracks_raw: list[dict[str, Any]] = library.get("tracks", [])
        return {str(t.get("id", "")) for t in tracks_raw if t.get("id")}

    async def add_likes(self, track_ids: list[str]) -> bool:
        """Add tracks to likes. Returns True on success."""
        await self._request(
            "POST",
            f"/users/{self._user_id}/likes/tracks/add-multiple",
            data={"track-ids": ",".join(track_ids)},
        )
        return True

    async def remove_likes(self, track_ids: list[str]) -> bool:
        """Remove tracks from likes. Returns True on success."""
        await self._request(
            "POST",
            f"/users/{self._user_id}/likes/tracks/remove",
            data={"track-ids": ",".join(track_ids)},
        )
        return True

    # ── Lifecycle ─────────────────────────────────────────

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


# ── Response parsers ──────────────────────────────────────


def _parse_track(raw: dict[str, Any]) -> YMTrack:
    """Parse a raw track dict from YM API into YMTrack."""
    return YMTrack(
        id=str(raw.get("id", "")),
        title=raw.get("title", ""),
        duration_ms=raw.get("durationMs"),
        artists=[
            {"id": str(a.get("id", "")), "name": a.get("name", "")} for a in raw.get("artists", [])
        ],
        albums=[
            {
                "id": str(a.get("id", "")),
                "title": a.get("title", ""),
                "year": a.get("year"),
                "genre": a.get("genre"),
            }
            for a in raw.get("albums", [])
        ],
        cover_uri=raw.get("coverUri"),
        explicit=raw.get("explicit", False),
    )


def _parse_album(raw: dict[str, Any]) -> YMAlbum:
    """Parse a raw album dict from YM API into :class:`YMAlbum`.

    When fetched via ``/albums/{id}/with-tracks`` the YM response nests
    tracks inside ``volumes`` (one list per disc). We flatten them so
    callers always see ``album.tracks`` as a single list. Regular
    ``/albums/{id}`` responses leave ``tracks`` empty.
    """
    volumes = raw.get("volumes") or []
    parsed_tracks: list[YMTrack] = []
    if isinstance(volumes, list):
        for vol in volumes:
            if not isinstance(vol, list):
                continue
            for track_raw in vol:
                if isinstance(track_raw, dict):
                    parsed_tracks.append(_parse_track(track_raw))

    return YMAlbum(
        id=str(raw.get("id", "")),
        title=raw.get("title", ""),
        track_count=raw.get("trackCount"),
        artists=[
            {"id": str(a.get("id", "")), "name": a.get("name", "")} for a in raw.get("artists", [])
        ],
        year=raw.get("year"),
        genre=raw.get("genre"),
        tracks=parsed_tracks,
    )


def _parse_artist(raw: dict[str, Any]) -> YMArtist:
    """Parse a raw artist dict from YM API into YMArtist."""
    return YMArtist(
        id=str(raw.get("id", "")),
        name=raw.get("name", ""),
    )


def _parse_playlist(raw: dict[str, Any]) -> YMPlaylist:
    """Parse a raw playlist dict from YM API into YMPlaylist."""
    owner = raw.get("owner", {})
    owner_id = owner.get("uid") if isinstance(owner, dict) else raw.get("uid")
    return YMPlaylist(
        kind=raw.get("kind", 0),
        owner_id=str(owner_id) if owner_id is not None else None,
        title=raw.get("title", ""),
        track_count=raw.get("trackCount"),
        visibility=raw.get("visibility"),
        revision=raw.get("revision"),
    )
