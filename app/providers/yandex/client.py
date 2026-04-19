"""Yandex Music async HTTP client — httpx + OAuth + rate limiter.

Ported from app/ym/client.py. All public methods return raw dicts (shape
defined by YM API); YandexAdapter maps them to v2 schemas.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import httpx

from app.providers.yandex.rate_limiter import TokenBucketRateLimiter


class YandexError(Exception):
    """Base Yandex client error."""


class AuthFailedError(YandexError):
    """HTTP 401 / 403 — invalid or missing token."""


class RateLimitedError(YandexError):
    """HTTP 429 — too many requests (after retries)."""


class APIError(YandexError):
    """HTTP 4xx (non-401/403/429) or 5xx."""


class YandexClient:
    def __init__(
        self,
        *,
        token: str,
        user_id: str,
        base_url: str = "https://api.music.yandex.net",
        rate_limiter: TokenBucketRateLimiter | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self._token = token
        self._user_id = user_id
        self._base_url = base_url.rstrip("/")
        self._rate_limiter = rate_limiter or TokenBucketRateLimiter()
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"OAuth {token}"},
            timeout=timeout_s,
        )
        self._closed = False

    # ---------- core request ---------- #

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        await self._rate_limiter.acquire()
        try:
            resp = await self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise APIError(f"HTTP transport error: {exc}") from exc

        if resp.status_code == 401 or resp.status_code == 403:
            raise AuthFailedError(f"auth failed: {resp.status_code} — check DJ_YM_TOKEN")
        if resp.status_code == 429:
            await self._rate_limiter.on_rate_limited()
            if self._rate_limiter.retries_exhausted():
                raise RateLimitedError("rate limited, retries exhausted")
            raise RateLimitedError(f"rate limited, retry_after={resp.headers.get('Retry-After')}")
        if resp.status_code >= 400:
            raise APIError(f"{resp.status_code}: {resp.text[:500]}")

        self._rate_limiter.on_success()
        payload = resp.json()
        return payload.get("result", payload) if isinstance(payload, dict) else payload

    # ---------- search ---------- #

    _SEARCH_TYPE_ALIASES: ClassVar[dict[str, str]] = {
        "tracks": "track",
        "albums": "album",
        "artists": "artist",
        "playlists": "playlist",
    }

    async def search(
        self,
        *,
        query: str,
        type: str = "track",
        limit: int = 20,
        page: int = 0,
    ) -> dict[str, Any]:
        # YM expects singular entity names and a mandatory `page` parameter;
        # accept the plural aliases used by the MCP tool surface for convenience.
        ym_type = self._SEARCH_TYPE_ALIASES.get(type, type)
        return await self._request(
            "GET",
            "/search",
            params={
                "text": query,
                "type": ym_type,
                "page": page,
                "page-size": limit,
            },
        )

    # ---------- tracks ---------- #

    async def get_tracks(self, track_ids: list[str]) -> list[dict[str, Any]]:
        res = await self._request("GET", "/tracks", params={"trackIds": ",".join(track_ids)})
        return res if isinstance(res, list) else []

    async def get_similar(self, track_id: str) -> list[dict[str, Any]]:
        res = await self._request("GET", f"/tracks/{track_id}/similar")
        if isinstance(res, dict):
            return list(res.get("similarTracks", []))
        return []

    async def get_download_info(self, track_id: str) -> list[dict[str, Any]]:
        res = await self._request("GET", f"/tracks/{track_id}/download-info")
        return res if isinstance(res, list) else []

    async def download_track(self, track_id: str, dest: Path) -> Path:
        """Resolve signed MP3 URL via XML manifest + MD5, then stream to disk.

        YM's download pipeline has three hops: `/tracks/{id}/download-info`
        lists codec/bitrate variants; each variant's `downloadInfoUrl` returns
        an XML manifest with `host`, `path`, `s` (salt), `ts`; the playable
        MP3 lives at `https://{host}/get-mp3/{md5(SALT+path[1:]+s)}/{ts}{path}`.
        """
        info = await self.get_download_info(track_id)
        if not info:
            raise APIError(f"no download options for track {track_id}")
        best = max(info, key=lambda x: x.get("bitrateInKbps", 0))
        manifest_url = best["downloadInfoUrl"]

        manifest = await self._http.get(manifest_url)
        if manifest.status_code >= 400:
            raise APIError(f"download manifest failed: {manifest.status_code}")
        signed_url = self._build_signed_mp3_url(manifest.text)

        dest.parent.mkdir(parents=True, exist_ok=True)
        async with self._http.stream("GET", signed_url) as resp:
            if resp.status_code >= 400:
                raise APIError(f"download failed: {resp.status_code}")
            with dest.open("wb") as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)
        return dest

    _DOWNLOAD_SALT: ClassVar[str] = "XGRlBW9FXlekgbPrRHuSiA"

    @classmethod
    def _build_signed_mp3_url(cls, manifest_xml: str) -> str:
        import hashlib
        import xml.etree.ElementTree as ET

        root = ET.fromstring(manifest_xml)
        host = root.findtext("host")
        path = root.findtext("path")
        s = root.findtext("s")
        ts = root.findtext("ts")
        if not (host and path and s is not None and ts):
            raise APIError(f"bad download manifest: {manifest_xml[:200]}")
        sign = hashlib.md5((cls._DOWNLOAD_SALT + path[1:] + s).encode()).hexdigest()
        return f"https://{host}/get-mp3/{sign}/{ts}{path}"

    # ---------- albums + artists ---------- #

    async def get_album(self, album_id: str, *, with_tracks: bool = False) -> dict[str, Any]:
        path = f"/albums/{album_id}" + ("/with-tracks" if with_tracks else "")
        return await self._request("GET", path)

    async def get_artist_tracks(
        self, artist_id: str, *, offset: int = 0, limit: int = 50
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/artists/{artist_id}/tracks",
            params={"page": offset // limit, "page-size": limit},
        )

    # ---------- playlists ---------- #

    def _split_playlist_id(self, playlist_id: str | int) -> tuple[str, str]:
        """Accept "owner:kind", plain kind, or int kind; fall back to self._user_id.

        YM identifies a playlist by (owner_uid, kind). Historically our callers
        pass the composite "owner:kind"; newer callers may pass the bare kind
        after create_playlist returns it. Both shapes must work.
        """
        raw = str(playlist_id)
        if ":" in raw:
            owner, kind = raw.split(":", 1)
            return owner, kind
        return str(self._user_id), raw

    async def get_playlist(self, playlist_id: str | int) -> dict[str, Any]:
        owner, kind = self._split_playlist_id(playlist_id)
        return await self._request("GET", f"/users/{owner}/playlists/{kind}")

    async def list_playlists(self) -> list[dict[str, Any]]:
        res = await self._request("GET", f"/users/{self._user_id}/playlists/list")
        return res if isinstance(res, list) else []

    async def create_playlist(self, *, title: str, visibility: str = "private") -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/users/{self._user_id}/playlists/create",
            data={"title": title, "visibility": visibility},
        )

    async def modify_playlist(
        self, playlist_id: str | int, *, diff: list[dict[str, Any]], revision: int
    ) -> dict[str, Any]:
        owner, kind = self._split_playlist_id(playlist_id)
        import json as _json

        return await self._request(
            "POST",
            f"/users/{owner}/playlists/{kind}/change-relative",
            data={"diff": _json.dumps(diff), "revision": revision},
        )

    async def delete_playlist(self, playlist_id: str | int) -> dict[str, Any]:
        owner, kind = self._split_playlist_id(playlist_id)
        return await self._request("POST", f"/users/{owner}/playlists/{kind}/delete")

    async def rename_playlist(self, playlist_id: str | int, *, title: str) -> dict[str, Any]:
        owner, kind = self._split_playlist_id(playlist_id)
        return await self._request(
            "POST", f"/users/{owner}/playlists/{kind}/name", data={"value": title}
        )

    async def set_playlist_description(
        self, playlist_id: str | int, *, description: str
    ) -> dict[str, Any]:
        owner, kind = self._split_playlist_id(playlist_id)
        return await self._request(
            "POST",
            f"/users/{owner}/playlists/{kind}/description",
            data={"value": description},
        )

    # ---------- likes ---------- #

    async def get_liked_ids(self) -> list[str]:
        res = await self._request("GET", f"/users/{self._user_id}/likes/tracks")
        if isinstance(res, dict):
            library = res.get("library", {})
            return [str(t["id"]) for t in library.get("tracks", [])]
        return []

    async def get_disliked_ids(self) -> list[str]:
        res = await self._request("GET", f"/users/{self._user_id}/dislikes/tracks")
        if isinstance(res, dict):
            library = res.get("library", {})
            return [str(t["id"]) for t in library.get("tracks", [])]
        return []

    async def add_likes(self, track_ids: list[str]) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/users/{self._user_id}/likes/tracks/add-multiple",
            data={"track-ids": ",".join(track_ids)},
        )

    async def remove_likes(self, track_ids: list[str]) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/users/{self._user_id}/likes/tracks/remove",
            data={"track-ids": ",".join(track_ids)},
        )

    # ---------- cleanup ---------- #

    async def close(self) -> None:
        if self._closed:
            return
        await self._http.aclose()
        self._closed = True
