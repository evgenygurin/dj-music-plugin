"""Async client for a Suno-compatible authorized REST generation API."""

from __future__ import annotations

import time
from base64 import b64encode
from pathlib import Path
from typing import Any, ClassVar, cast
from urllib.parse import urlsplit

import httpx

from app.providers.suno.client_errors import (
    APIError,
    AudioNotReadyError,
    AuthFailedError,
    RateLimitedError,
    SunoError,
)
from app.providers.suno.session_auth import SunoSessionCredentials
from app.providers.yandex.rate_limiter import TokenBucketRateLimiter


class SunoClient:
    """HTTP client with configurable endpoint paths.

    The public surface deliberately speaks in generic generation terms because
    Suno-compatible providers vary in field names. The adapter above this
    client normalizes common ID/status/audio URL aliases.
    """

    _AUDIO_URL_KEYS: ClassVar[tuple[str, ...]] = (
        "audio_url",
        "audioUrl",
        "download_url",
        "downloadUrl",
        "streamAudioUrl",
        "stream_audio_url",
        "sourceAudioUrl",
        "source_audio_url",
        "url",
    )

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str,
        generate_path: str = "/v1/generations",
        status_path: str = "/v1/generations/{id}",
        cancel_path: str = "/v1/generations/{id}/cancel",
        download_path: str = "",
        captcha_check_path: str = "/api/c/check",
        account_path: str = "/api/billing/info/",
        upload_base_url: str = "https://sunoapiorg.redpandaai.co",
        auth_header: str = "Authorization",
        auth_scheme: str = "Bearer",
        session_auth: SunoSessionCredentials | None = None,
        clerk_url: str = "https://auth.suno.com",
        clerk_api_version: str = "2025-11-10",
        clerk_js_version: str = "5.117.0",
        rate_limiter: TokenBucketRateLimiter | None = None,
        timeout_s: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._generate_path = generate_path
        self._status_path = status_path
        self._cancel_path = cancel_path
        self._download_path = download_path
        self._captcha_check_path = captcha_check_path
        self._account_path = account_path
        self._upload_base_url = upload_base_url.rstrip("/")
        self._auth_header = auth_header
        self._auth_scheme = auth_scheme
        self._session_auth = session_auth
        self._clerk_url = clerk_url.rstrip("/")
        self._clerk_api_version = clerk_api_version
        self._clerk_js_version = clerk_js_version
        self._rate_limiter = rate_limiter or TokenBucketRateLimiter()
        self._http = httpx.AsyncClient(base_url=self._base_url, timeout=timeout_s)
        self._clerk_session_id: str | None = None
        self._bearer_token: str | None = None
        self._token_refreshed_at: float = 0.0
        self._closed = False

    async def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._api_key:
            value = self._api_key
            if self._auth_scheme:
                value = f"{self._auth_scheme} {value}"
            headers[self._auth_header] = value

        if self._session_auth is not None:
            auth = await self._session_auth.ensure_authenticated()
            if auth.cookie_header:
                headers["Cookie"] = auth.cookie_header
            headers["Origin"] = "https://suno.com"
            headers["Referer"] = "https://suno.com/"
            headers["browser-token"] = self._build_browser_token()
            if auth.device_id:
                headers["device-id"] = auth.device_id
            if not self._api_key:
                token = auth.bearer_token
                if not token and auth.client_token:
                    token = await self._ensure_clerk_bearer(auth.client_token, auth.cookie_header)
                if token:
                    headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _download_headers(self, url: str) -> dict[str, str]:
        """Auth headers for an audio download.

        Suno serves generation audio from pre-signed CDN hosts
        (``cdn1.suno.ai`` / ``audiopipe.suno.ai``), which need no auth. Sending
        the Clerk bearer JWT, session cookies, ``browser-token`` and
        ``device-id`` to an off-host CDN leaks session credentials and can be
        rejected by the CDN. Only attach auth when the URL is same-origin
        (relative path or a host matching ``base_url``).
        """
        if url.startswith("http://") or url.startswith("https://"):
            base_host = urlsplit(self._base_url).netloc.lower()
            target_host = urlsplit(url).netloc.lower()
            if target_host and target_host != base_host:
                return {}
        return await self._headers()

    @staticmethod
    def _build_browser_token() -> str:
        payload = f'{{"timestamp":{int(time.time() * 1000)}}}'
        return b64encode(payload.encode("utf-8")).decode("ascii")

    async def _ensure_clerk_bearer(self, client_token: str, cookie_header: str) -> str | None:
        now = time.monotonic()
        if self._bearer_token and now - self._token_refreshed_at < 50:
            return self._bearer_token

        headers = {
            "Authorization": client_token,
            "Cookie": cookie_header,
        }
        params = {
            "__clerk_api_version": self._clerk_api_version,
            "_clerk_js_version": self._clerk_js_version,
        }
        try:
            if self._clerk_session_id is None:
                resp = await self._http.get(
                    f"{self._clerk_url}/v1/client", params=params, headers=headers
                )
                if resp.status_code >= 400:
                    raise AuthFailedError(f"Clerk session lookup failed: {resp.status_code}")
                self._clerk_session_id = self._extract_clerk_session_id(resp.json())
            if not self._clerk_session_id:
                return None
            resp = await self._http.post(
                f"{self._clerk_url}/v1/client/sessions/{self._clerk_session_id}/tokens",
                params=params,
                headers=headers,
                json={},
            )
            if resp.status_code >= 400:
                raise AuthFailedError(f"Clerk token refresh failed: {resp.status_code}")
            self._bearer_token = self._extract_clerk_jwt(resp.json())
            self._token_refreshed_at = now
            return self._bearer_token
        except httpx.HTTPError as exc:
            raise APIError(f"Clerk transport error: {exc}") from exc

    @staticmethod
    def _extract_clerk_session_id(payload: dict[str, Any]) -> str | None:
        response = payload.get("response") if isinstance(payload, dict) else None
        if isinstance(response, dict):
            sid = response.get("last_active_session_id")
            if sid:
                return str(sid)
            sessions = response.get("sessions")
            if isinstance(sessions, list):
                for session in sessions:
                    if isinstance(session, dict) and session.get("id"):
                        return str(session["id"])
        return None

    @staticmethod
    def _extract_clerk_jwt(payload: dict[str, Any]) -> str | None:
        if isinstance(payload.get("jwt"), str):
            return str(payload["jwt"])
        response = payload.get("response") if isinstance(payload, dict) else None
        if isinstance(response, dict) and isinstance(response.get("jwt"), str):
            return str(response["jwt"])
        return None

    def _path(self, template: str, generation_id: str | None = None) -> str:
        if generation_id is not None:
            template = template.replace("{id}", generation_id)
        return "/" + template.lstrip("/")

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        await self._rate_limiter.acquire()
        try:
            headers = await self._headers()
            resp = await self._http.request(
                method,
                path,
                headers={**headers, **kwargs.pop("headers", {})},
                **kwargs,
            )
        except httpx.HTTPError as exc:
            raise APIError(f"HTTP transport error: {exc}") from exc

        if resp.status_code in (401, 403):
            hint = (
                "refresh the bearer (uv run python scripts/suno_refresh_token.py) — "
                "session JWTs expire ~hourly"
                if self._session_auth is not None
                else "check DJ_SUNO_API_KEY"
            )
            raise AuthFailedError(f"auth failed: {resp.status_code} — {hint}")
        if resp.status_code == 429:
            await self._rate_limiter.on_rate_limited()
            if self._rate_limiter.retries_exhausted():
                raise RateLimitedError("rate limited, retries exhausted")
            raise RateLimitedError(f"rate limited, retry_after={resp.headers.get('Retry-After')}")
        if resp.status_code >= 400:
            raise APIError(f"{resp.status_code}: {resp.text[:500]}")

        self._rate_limiter.on_success()
        if not resp.content:
            return {}
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = resp.json()
            if isinstance(payload, dict) and "code" in payload:
                code = payload.get("code")
                if code not in (None, 200):
                    message = str(payload.get("msg") or payload.get("message") or "")
                    if code in (401, 403):
                        raise AuthFailedError(f"auth failed: {code}: {message}")
                    if code in (405, 429, 430):
                        await self._rate_limiter.on_rate_limited()
                        raise RateLimitedError(f"rate limited: {code}: {message}")
                    raise APIError(f"Suno API error {code}: {message}")
            return payload.get("data", payload) if isinstance(payload, dict) else payload
        return resp

    async def create_generation(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._session_auth is not None and self._captcha_check_path:
            await self._check_captcha()
        return cast(
            dict[str, Any],
            await self._request("POST", self._path(self._generate_path), json=payload),
        )

    async def get_generation(self, generation_id: str) -> dict[str, Any]:
        payload = await self._request("GET", self._path(self._status_path, generation_id))
        # Suno web /api/feed/v2/ returns {"clips": [...]}; SunoAPI returns a
        # task object with response.sunoData. Unwrap only the web feed shape.
        if isinstance(payload, dict) and isinstance(payload.get("clips"), list):
            clips = payload["clips"]
            return cast(dict[str, Any], clips[0] if clips else {})
        if isinstance(payload, list):
            return cast(dict[str, Any], payload[0] if payload else {})
        return cast(dict[str, Any], payload)

    async def _check_captcha(self) -> None:
        """Best-effort pre-generation CAPTCHA gate.

        Suno's ``/api/c/check`` is a POST that expects a ``ctype`` body; it has
        drifted before (older builds answered GET). The pre-check must never be
        the reason a generation is blocked, so endpoint drift (405/422/404) and
        other non-auth API errors are swallowed — a genuine challenge is still
        surfaced by the real generate call. Only a clean response that
        explicitly reports a required challenge, or an auth failure, aborts.
        """
        try:
            payload = await self._request(
                "POST",
                self._path(self._captcha_check_path),
                json={"ctype": "generation"},
            )
        except AuthFailedError:
            raise
        except SunoError:
            return
        required = isinstance(payload, dict) and (
            payload.get("required") is True or payload.get("captcha_required") is True
        )
        if required:
            raise AuthFailedError(
                "Suno requires a CAPTCHA/challenge for this account or IP; "
                "complete it in the browser and retry"
            )

    async def cancel_generation(self, generation_id: str) -> dict[str, Any]:
        if not self._cancel_path:
            raise APIError("cancel endpoint is not configured for this Suno provider")
        return cast(
            dict[str, Any],
            await self._request("POST", self._path(self._cancel_path, generation_id)),
        )

    async def get_account(self) -> dict[str, Any]:
        """Fetch account/billing info (credits, plan). Empty path -> {}."""
        if not self._account_path:
            return {}
        payload = await self._request("GET", self._path(self._account_path))
        if isinstance(payload, int):
            return {"credits_left": payload}
        return cast(dict[str, Any], payload if isinstance(payload, dict) else {})

    async def api_call(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        absolute: bool = False,
    ) -> Any:
        """Generic sunoapi.org REST call — reuses auth, rate limit, error mapping.

        ``absolute=True`` passes ``path`` through untouched (used for the
        file-upload host, which differs from ``base_url``). Otherwise the path
        is normalized against the configured base URL.
        """
        url = path if absolute else self._path(path)
        kwargs: dict[str, Any] = {}
        if json is not None:
            kwargs["json"] = json
        if params is not None:
            kwargs["params"] = params
        if data is not None:
            kwargs["data"] = data
        if files is not None:
            kwargs["files"] = files
        return await self._request(method, url, **kwargs)

    async def upload_file(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        """POST to the file-upload host (``upload_base_url``, off the API host)."""
        url = f"{self._upload_base_url}/{path.lstrip('/')}"
        return await self.api_call("POST", url, json=json, data=data, files=files, absolute=True)

    async def download_generation(
        self,
        generation_id: str,
        dest: Path,
        *,
        audio_url: str | None = None,
    ) -> Path:
        url = audio_url
        if not url and self._download_path:
            url = self._path(self._download_path, generation_id)
        if not url:
            generation = await self.get_generation(generation_id)
            url = self.find_audio_url(generation)
        if not url:
            raise AudioNotReadyError(f"generation {generation_id!r} has no audio URL yet")

        await self._rate_limiter.acquire()
        try:
            headers = await self._download_headers(url)
            request = self._http.stream("GET", url, headers=headers)
            dest.parent.mkdir(parents=True, exist_ok=True)
            async with request as resp:
                if resp.status_code in (401, 403):
                    raise AuthFailedError(f"auth failed: {resp.status_code}")
                if resp.status_code == 429:
                    await self._rate_limiter.on_rate_limited()
                    raise RateLimitedError("rate limited while downloading generation audio")
                if resp.status_code >= 400:
                    detail = (await resp.aread()).decode(errors="replace")[:200]
                    raise APIError(f"download failed: {resp.status_code}: {detail}")
                with dest.open("wb") as f:
                    async for chunk in resp.aiter_bytes():
                        f.write(chunk)
        except httpx.HTTPError as exc:
            raise APIError(f"HTTP transport error: {exc}") from exc

        self._rate_limiter.on_success()
        return dest

    @classmethod
    def find_audio_url(cls, payload: dict[str, Any]) -> str | None:
        for key in cls._AUDIO_URL_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value

        for container_key in (
            "data",
            "response",
            "sunoData",
            "clips",
            "tracks",
            "generations",
            "items",
            "results",
        ):
            value = payload.get(container_key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        found = cls.find_audio_url(item)
                        if found:
                            return found
            elif isinstance(value, dict):
                found = cls.find_audio_url(value)
                if found:
                    return found
        return None

    async def close(self) -> None:
        if self._closed:
            return
        await self._http.aclose()
        self._closed = True
