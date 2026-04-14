"""HTTP audio stream proxy (provider-agnostic).

Resolves a temporary signed URL via MusicProvider.get_stream_url(),
caches it, and streams audio bytes to the browser with HTTP range support.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.api.signed_url_cache import SignedUrlCache

logger = logging.getLogger(__name__)


class AudioStreamProxy:
    """Range-aware audio proxy with signed URL caching.

    Uses ``MusicProvider.get_stream_url()`` to resolve CDN URLs.
    """

    def __init__(
        self,
        *,
        signed_url_cache: SignedUrlCache,
        get_provider: Callable[[], Any | None],
    ) -> None:
        self._signed_url_cache = signed_url_cache
        self._get_provider = get_provider

    def _require_provider(self) -> Any:
        provider = self._get_provider()
        if provider is None:
            raise HTTPException(status_code=503, detail="Music provider not initialised")
        return provider

    async def get_signed_url(self, track_id: str) -> str:
        """Resolve and cache a signed download URL via MusicProvider."""
        cached = self._signed_url_cache.get(track_id)
        if cached is not None:
            return cached

        provider = self._require_provider()

        try:
            signed_url = await provider.get_stream_url(track_id)
        except Exception as exc:
            status = getattr(exc, "status_code", 502)
            raise HTTPException(status_code=status, detail=str(exc)) from exc

        self._signed_url_cache.set(track_id, signed_url)
        return signed_url

    async def _open_upstream(
        self,
        signed_url: str,
        upstream_headers: dict[str, str],
    ) -> tuple[httpx.AsyncClient, httpx.Response]:
        """Open a streaming connection to the CDN."""
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

    async def stream(self, track_id: str, range_header: str | None = None) -> StreamingResponse:
        """Proxy-stream an audio file to the browser.

        On upstream failure, invalidates the signed URL cache and retries
        once with a fresh URL (handles expired CDN links).
        """
        upstream_headers: dict[str, str] = {}
        if range_header:
            upstream_headers["Range"] = range_header

        signed_url = await self.get_signed_url(track_id)

        try:
            client, upstream = await self._open_upstream(signed_url, upstream_headers)
        except (httpx.HTTPError, HTTPException):
            self._signed_url_cache.delete(track_id)
            signed_url = await self.get_signed_url(track_id)
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
                logger.warning("audio stream %s interrupted: %s", track_id, exc)
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


# Backward-compat alias
YmAudioProxy = AudioStreamProxy
