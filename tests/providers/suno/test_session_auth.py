"""Suno session auth tests without launching a browser."""

from __future__ import annotations

import json

import pytest

from app.providers.suno.client_errors import AuthFailedError
from app.providers.suno.session_auth import SunoSessionCredentials


@pytest.mark.asyncio
async def test_ensure_authenticated_loads_saved_storage_state(tmp_path) -> None:
    state_path = tmp_path / "storage_state.json"
    state_path.write_text(
        json.dumps(
            {
                "cookies": [
                    {"name": "__client", "value": "client-token", "domain": ".suno.com"},
                    {"name": "suno_device_id", "value": "device-1", "domain": ".suno.com"},
                ],
                "bearer_token": "jwt-token",
            }
        ),
        encoding="utf-8",
    )
    session = SunoSessionCredentials(storage_state_path=state_path)
    auth = await session.ensure_authenticated()
    assert auth.client_token == "client-token"
    assert auth.device_id == "device-1"
    assert auth.bearer_token == "jwt-token"
    assert auth.cookie_header == "__client=client-token; suno_device_id=device-1"


@pytest.mark.asyncio
async def test_ensure_authenticated_uses_explicit_values() -> None:
    session = SunoSessionCredentials(
        cookie_header="__client=client-token; suno_device_id=device-1",
        bearer_token="jwt-token",
    )
    auth = await session.ensure_authenticated()
    assert auth.client_token == "client-token"
    assert auth.device_id == "device-1"
    assert auth.bearer_token == "jwt-token"


@pytest.mark.asyncio
async def test_ensure_authenticated_extracts_session_cookie_as_bearer() -> None:
    session = SunoSessionCredentials(
        cookie_header="__client=client-token; __session=jwt-token; ajs_anonymous_id=device-1",
    )
    auth = await session.ensure_authenticated()
    assert auth.client_token == "client-token"
    assert auth.device_id == "device-1"
    assert auth.bearer_token == "jwt-token"


@pytest.mark.asyncio
async def test_ensure_authenticated_requires_session_credentials(tmp_path) -> None:
    session = SunoSessionCredentials(storage_state_path=tmp_path / "missing.json")
    with pytest.raises(AuthFailedError, match="DJ_SUNO_COOKIE_HEADER"):
        await session.ensure_authenticated()


@pytest.mark.asyncio
async def test_ensure_authenticated_requires_device_with_bearer() -> None:
    session = SunoSessionCredentials(bearer_token="jwt-token")
    with pytest.raises(AuthFailedError, match="DJ_SUNO_DEVICE_ID"):
        await session.ensure_authenticated()


@pytest.mark.asyncio
async def test_ensure_authenticated_requires_token_with_device() -> None:
    session = SunoSessionCredentials(device_id="device-1")
    with pytest.raises(AuthFailedError, match="bearer JWT or __client"):
        await session.ensure_authenticated()
