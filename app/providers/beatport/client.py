"""Beatport v4 async HTTP client — httpx + OAuth code flow + rate limiter.

Auth mirrors the Serato-DJ-Lite OAuth flow (also used by orpheusdl-beatport):

    1. GET  auth/o/authorize/   (302, sets session cookies)
    2. POST auth/login/         (username + password)
    3. GET  auth/o/authorize/   (302 → ?code=...)
    4. POST auth/o/token/       (grant_type=authorization_code → access/refresh)

All public methods return raw dicts (shape defined by the Beatport API);
``BeatportAdapter`` maps them to our normalized shape.
"""

from __future__ import annotations

import time
from typing import Any, ClassVar, cast

import httpx

from app.providers.beatport.rate_limiter import TokenBucketRateLimiter

_WEB_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_API_UA = "libbeatport/v2.8.2"


class BeatportError(Exception):
    """Base Beatport client error."""


class AuthFailedError(BeatportError):
    """Login / token exchange failed — check DJ_BEATPORT_USERNAME/PASSWORD."""


class RateLimitedError(BeatportError):
    """HTTP 429 — too many requests (after retries)."""


class APIError(BeatportError):
    """HTTP 4xx (non-401/403/429) or 5xx."""


class SubscriptionRequiredError(BeatportError):
    """Audio stream/download needs a paid Beatport Streaming subscription."""


class BeatportClient:
    _SEARCH_TYPE_ALIASES: ClassVar[dict[str, str]] = {
        "track": "tracks",
        "artist": "artists",
        "release": "releases",
        "label": "labels",
    }

    def __init__(
        self,
        *,
        username: str,
        password: str,
        client_id: str,
        redirect_uri: str,
        base_url: str = "https://api.beatport.com/v4",
        rate_limiter: TokenBucketRateLimiter | None = None,
        retry_attempts: int = 3,
        timeout_s: float = 30.0,
    ) -> None:
        self._username = username
        self._password = password
        self._client_id = client_id
        self._redirect_uri = redirect_uri
        self._base_url = base_url.rstrip("/")
        self._rate_limiter = rate_limiter or TokenBucketRateLimiter()
        self._retry_attempts = retry_attempts
        # A single cookie-persisting client carries the OAuth session cookies
        # across the authorize → login → authorize hops.
        self._http = httpx.AsyncClient(timeout=timeout_s, follow_redirects=False)
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0.0
        self._closed = False

    # ---------- auth ---------- #

    @property
    def _authorize_params(self) -> dict[str, str]:
        return {
            "client_id": self._client_id,
            "response_type": "code",
            "redirect_uri": self._redirect_uri,
        }

    async def authenticate(self) -> None:
        """Run the full OAuth code flow and store the tokens."""
        if not (self._username and self._password):
            raise AuthFailedError("no Beatport credentials — set DJ_BEATPORT_USERNAME/PASSWORD")
        url = f"{self._base_url}/auth/o/authorize/"
        h = {"User-Agent": _WEB_UA}

        r = await self._http.get(url, params=self._authorize_params, headers=h)
        if r.status_code != 302:
            raise AuthFailedError(f"authorize#1 expected 302, got {r.status_code}: {r.text[:200]}")
        loc = r.headers.get("location", "")
        referer = f"{r.url.scheme}://{r.url.host}{loc}" if loc.startswith("/") else loc

        r = await self._http.post(
            f"{self._base_url}/auth/login/",
            json={"username": self._username, "password": self._password},
            headers={**h, "Referer": referer},
        )
        if r.status_code != 200:
            raise AuthFailedError(f"login failed: {r.status_code}: {r.text[:200]}")

        r = await self._http.get(url, params=self._authorize_params, headers=h)
        if r.status_code != 302:
            raise AuthFailedError(f"authorize#2 expected 302, got {r.status_code}: {r.text[:200]}")
        loc = r.headers.get("location", "")
        if "code=" not in loc:
            raise AuthFailedError(f"no code in redirect: {loc[:200]}")
        code = loc.split("code=", 1)[1].split("&", 1)[0]

        r = await self._http.post(
            f"{self._base_url}/auth/o/token/",
            data={
                "client_id": self._client_id,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self._redirect_uri,
            },
        )
        if r.status_code != 200:
            raise AuthFailedError(f"token exchange failed: {r.status_code}: {r.text[:200]}")
        self._store_token(r.json())

    async def _refresh(self) -> None:
        if not self._refresh_token:
            await self.authenticate()
            return
        r = await self._http.post(
            f"{self._base_url}/auth/o/token/",
            data={
                "client_id": self._client_id,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if r.status_code != 200:
            # Refresh expired → fall back to a full login.
            await self.authenticate()
            return
        self._store_token(r.json())

    def _store_token(self, payload: dict[str, Any]) -> None:
        self._access_token = payload["access_token"]
        self._refresh_token = payload.get("refresh_token", self._refresh_token)
        # Refresh 60s early to avoid mid-request expiry.
        self._expires_at = time.monotonic() + max(0, int(payload.get("expires_in", 3600)) - 60)

    async def _ensure_token(self) -> None:
        if self._access_token is None:
            await self.authenticate()
        elif time.monotonic() >= self._expires_at:
            await self._refresh()

    # ---------- core request ---------- #

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        await self._ensure_token()
        await self._rate_limiter.acquire()
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = {"User-Agent": _API_UA, "Authorization": f"Bearer {self._access_token}"}
        try:
            resp = await self._http.get(
                url, params=params or {}, headers=headers, follow_redirects=True
            )
        except httpx.HTTPError as exc:
            raise APIError(f"HTTP transport error: {exc}") from exc

        if resp.status_code == 401:
            # Token rejected — refresh once and retry.
            await self._refresh()
            headers["Authorization"] = f"Bearer {self._access_token}"
            resp = await self._http.get(
                url, params=params or {}, headers=headers, follow_redirects=True
            )
            if resp.status_code == 401:
                # Still rejected after a fresh token → genuine auth failure.
                raise AuthFailedError("auth failed after refresh — check DJ_BEATPORT_* creds")
        if resp.status_code == 403:
            detail = ""
            try:
                detail = resp.json().get("detail", "")
            except Exception:
                detail = resp.text[:200]
            if "subscription" in detail.lower():
                raise SubscriptionRequiredError(f"Beatport subscription required: {detail}")
            raise AuthFailedError(f"forbidden: {detail}")
        if resp.status_code == 429:
            await self._rate_limiter.on_rate_limited()
            if self._rate_limiter.retries_exhausted():
                raise RateLimitedError("rate limited, retries exhausted")
            raise RateLimitedError(f"rate limited, retry_after={resp.headers.get('Retry-After')}")
        if resp.status_code >= 400:
            raise APIError(f"{resp.status_code}: {resp.text[:500]}")

        self._rate_limiter.on_success()
        return cast(dict[str, Any], resp.json())

    # ---------- catalog ---------- #

    async def search(
        self, *, query: str, type: str = "tracks", per_page: int = 10
    ) -> dict[str, Any]:
        bp_type = self._SEARCH_TYPE_ALIASES.get(type, type)
        return await self._get(
            "catalog/search/", params={"q": query, "type": bp_type, "per_page": per_page}
        )

    async def get_track(self, track_id: str) -> dict[str, Any]:
        return await self._get(f"catalog/tracks/{track_id}/")

    async def get_account(self) -> dict[str, Any]:
        return await self._get("auth/o/introspect/")

    # ---------- cleanup ---------- #

    async def close(self) -> None:
        if self._closed:
            return
        await self._http.aclose()
        self._closed = True
