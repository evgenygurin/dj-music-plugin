"""HTTP audio proxy for Yandex Music downloads."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from dj_music.api.services.signed_url_cache import SignedUrlCache

logger = logging.getLogger(__name__)


class YmAudioProxy:
    """Range-aware YM audio proxy with signed URL caching."""

    def __init__(
        self,
        *,
        signed_url_cache: SignedUrlCache,
        get_ym_client: Callable[[], Any | None],
    ) -> None:
        self._signed_url_cache = signed_url_cache
        self._get_ym_client = get_ym_client

    def _require_client(self) -> Any:
        client = self._get_ym_client()
        if client is None:
            raise HTTPException(status_code=503, detail="YM client not initialised")
        return client

    async def get_signed_url(self, ym_track_id: str) -> str:
        """Resolve and cache a signed YM download URL."""
        from dj_music.ym.client import APIError

        cached = self._signed_url_cache.get(ym_track_id)
        if cached is not None:
            return cached

        ym_client = self._require_client()

        try:
            infos = await ym_client.get_download_info(ym_track_id)
        except APIError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail=f"get_download_info failed: {exc}"
            ) from exc
        if not infos:
            raise HTTPException(status_code=404, detail=f"No download info for {ym_track_id}")

        best = infos[0]
        for info in infos:
            if info.get("codec") == "mp3":
                best = info
                break

        info_url = best.get("downloadInfoUrl")
        if not info_url:
            raise HTTPException(status_code=404, detail="downloadInfoUrl missing")

        try:
            signed_url = await ym_client._resolve_download_url(ym_track_id, info_url)
        except APIError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail=f"resolve_download_url failed: {exc}"
            ) from exc

        self._signed_url_cache.set(ym_track_id, signed_url)
        return signed_url

    async def _open_upstream(
        self,
        signed_url: str,
        upstream_headers: dict[str, str],
    ) -> tuple[httpx.AsyncClient, httpx.Response]:
        """Open a streaming connection to the YM CDN."""
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=15.0, write=10.0, pool=10.0),
            follow_redirects=True,
        )
        try:
            upstream = await client.send(
                client.build_request("GET", signed_url, headers=upstream_headers),
                stream=True,
            )
        except httpx.HTTPError:
            await client.aclose()
            raise
        if upstream.status_code >= 400:
            body = await upstream.aread()
            await upstream.aclose()
            await client.aclose()
            raise HTTPException(
                status_code=upstream.status_code,
                detail=f"Upstream {upstream.status_code}: {body[:200]!r}",
            )
        return client, upstream

    async def stream(self, ym_track_id: str, range_header: str | None = None) -> StreamingResponse:
        """Proxy-stream an audio file from YM to the browser.

        On upstream failure, invalidates the signed URL cache and retries
        once with a fresh URL (handles expired CDN links).
        """
        upstream_headers: dict[str, str] = {}
        if range_header:
            upstream_headers["Range"] = range_header

        signed_url = await self.get_signed_url(ym_track_id)

        try:
            client, upstream = await self._open_upstream(signed_url, upstream_headers)
        except (httpx.HTTPError, HTTPException):
            # First attempt failed — URL may have expired. Invalidate and retry.
            self._signed_url_cache.delete(ym_track_id)
            signed_url = await self.get_signed_url(ym_track_id)
            try:
                client, upstream = await self._open_upstream(signed_url, upstream_headers)
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=502, detail=f"Upstream fetch failed after retry: {exc}"
                ) from exc

        forward_keys = (
            "content-length",
            "content-range",
            "accept-ranges",
            "content-type",
            "last-modified",
            "etag",
        )
        response_headers: dict[str, str] = {"Cache-Control": "no-store"}
        for key in forward_keys:
            value = upstream.headers.get(key)
            if value is not None:
                response_headers[key] = value
        response_headers.setdefault("Accept-Ranges", "bytes")
        response_headers.setdefault("Content-Type", "audio/mpeg")

        async def _iter() -> Any:
            try:
                async for chunk in upstream.aiter_bytes(chunk_size=65536):
                    yield chunk
            except (httpx.ReadTimeout, httpx.ReadError, httpx.RemoteProtocolError) as exc:
                # Re-raise so Starlette sends a proper error instead of
                # silently closing the socket (which causes "other side closed"
                # in the Next.js panel proxy).
                logger.warning("audio stream %s interrupted: %s", ym_track_id, exc)
                raise
            finally:
                await upstream.aclose()
                await client.aclose()

        return StreamingResponse(
            _iter(),
            status_code=upstream.status_code,
            media_type=response_headers.get("Content-Type", "audio/mpeg"),
            headers=response_headers,
        )
