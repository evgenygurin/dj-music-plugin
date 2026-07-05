"""No-browser Suno web session credentials.

The provider does not automate Google/Suno login. A user-controlled browser
session supplies exported Suno/Clerk credentials via env vars or a JSON state
file, and this module normalizes them into headers for the HTTP client.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.providers.suno.client_errors import AuthFailedError


@dataclass(frozen=True, slots=True)
class SunoSessionAuth:
    cookies: list[dict[str, Any]]
    cookie_header: str
    client_token: str | None
    device_id: str | None = None
    bearer_token: str | None = None


class SunoSessionCredentials:
    """Load Suno session credentials without launching a browser."""

    def __init__(
        self,
        *,
        cookie_header: str = "",
        client_token: str = "",
        device_id: str = "",
        bearer_token: str = "",
        storage_state_path: Path | None = None,
    ) -> None:
        self._cookie_header = cookie_header.strip()
        self._client_token = client_token.strip()
        self._device_id = device_id.strip()
        self._bearer_token = bearer_token.strip()
        self._storage_state_path = storage_state_path.expanduser() if storage_state_path else None
        self._cached: SunoSessionAuth | None = None

    async def ensure_authenticated(self) -> SunoSessionAuth:
        if self._cached is not None:
            return self._cached

        explicit = self._from_explicit_values()
        if explicit is not None:
            self._cached = explicit
            return explicit

        saved = self._load_storage_state()
        if saved is not None:
            self._cached = saved
            return saved

        raise AuthFailedError(
            "Suno session auth requires DJ_SUNO_COOKIE_HEADER, "
            "DJ_SUNO_BEARER_TOKEN, DJ_SUNO_CLIENT_TOKEN, or a readable "
            "DJ_SUNO_STORAGE_STATE_PATH"
        )

    def _from_explicit_values(self) -> SunoSessionAuth | None:
        if not any((self._cookie_header, self._client_token, self._device_id, self._bearer_token)):
            return None

        cookies = self._cookies_from_header(self._cookie_header)
        client_token = self._client_token or self._extract_cookie(cookies, "__client")
        device_id = self._device_id or self._extract_device_id(cookies)
        bearer_token = self._bearer_token or self._extract_cookie(cookies, "__session")
        cookie_header = self._cookie_header
        if not cookie_header:
            parts = []
            if client_token:
                parts.append(f"__client={client_token}")
            if device_id:
                parts.append(f"suno_device_id={device_id}")
            cookie_header = "; ".join(parts)
            cookies = self._cookies_from_header(cookie_header)

        return self._validate_auth(
            SunoSessionAuth(
                cookies=cookies,
                cookie_header=cookie_header,
                client_token=client_token,
                device_id=device_id,
                bearer_token=bearer_token or None,
            )
        )

    def _validate_auth(self, auth: SunoSessionAuth) -> SunoSessionAuth:
        if not (auth.bearer_token or auth.client_token):
            raise AuthFailedError(
                "Suno session auth requires a Clerk bearer JWT or __client token"
            )
        if not auth.device_id:
            raise AuthFailedError(
                "Suno session auth requires DJ_SUNO_DEVICE_ID or a suno_device_id cookie"
            )
        if not (auth.cookie_header or auth.bearer_token):
            raise AuthFailedError(
                "Suno session auth requires DJ_SUNO_COOKIE_HEADER when no bearer JWT is set"
            )
        return auth

    def _load_storage_state(self) -> SunoSessionAuth | None:
        if self._storage_state_path is None or not self._storage_state_path.exists():
            return None
        try:
            payload = json.loads(self._storage_state_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise AuthFailedError(
                f"failed to read Suno storage state {self._storage_state_path}: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            return None

        if isinstance(payload.get("cookie_header"), str):
            cookies = self._cookies_from_header(payload["cookie_header"])
            return self._validate_auth(
                SunoSessionAuth(
                    cookies=cookies,
                    cookie_header=payload["cookie_header"],
                    client_token=str(payload.get("client_token") or "")
                    or self._extract_cookie(cookies, "__client"),
                    device_id=str(payload.get("device_id") or "")
                    or self._extract_device_id(cookies),
                    bearer_token=str(payload.get("bearer_token") or "")
                    or self._extract_cookie(cookies, "__session"),
                )
            )

        raw_cookies = payload.get("cookies")
        if isinstance(raw_cookies, list) and raw_cookies:
            typed_cookies = [c for c in raw_cookies if isinstance(c, dict)]
            return self._from_cookies(
                typed_cookies,
                bearer_token=str(payload.get("bearer_token") or "") or None,
            )
        return None

    def _from_cookies(
        self,
        cookies: list[dict[str, Any]],
        *,
        bearer_token: str | None = None,
    ) -> SunoSessionAuth:
        cookie_pairs: list[str] = []
        client_token: str | None = None
        device_id: str | None = None
        for cookie in cookies:
            name = cookie.get("name")
            value = cookie.get("value")
            if not isinstance(name, str) or not isinstance(value, str):
                continue
            cookie_pairs.append(f"{name}={value}")
            if name == "__client":
                client_token = value
            if name in {"suno_device_id", "device_id", "ajs_anonymous_id"} and device_id is None:
                device_id = value
        bearer_token = bearer_token or self._extract_cookie(cookies, "__session")
        return self._validate_auth(
            SunoSessionAuth(
                cookies=cookies,
                cookie_header="; ".join(cookie_pairs),
                client_token=client_token,
                device_id=device_id,
                bearer_token=bearer_token,
            )
        )

    @staticmethod
    def _cookies_from_header(cookie_header: str) -> list[dict[str, str]]:
        cookies: list[dict[str, str]] = []
        for pair in cookie_header.split(";"):
            name, sep, value = pair.strip().partition("=")
            if sep and name:
                cookies.append({"name": name, "value": value})
        return cookies

    @staticmethod
    def _extract_cookie(cookies: list[dict[str, Any]], name: str) -> str | None:
        for cookie in cookies:
            if cookie.get("name") == name and isinstance(cookie.get("value"), str):
                return str(cookie["value"])
        return None

    @classmethod
    def _extract_device_id(cls, cookies: list[dict[str, Any]]) -> str | None:
        for name in ("suno_device_id", "device_id", "ajs_anonymous_id"):
            value = cls._extract_cookie(cookies, name)
            if value:
                return value
        return None
