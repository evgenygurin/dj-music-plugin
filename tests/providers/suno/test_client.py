"""SunoClient tests that do not require a live Suno API."""

from __future__ import annotations

import json
from base64 import b64decode
from unittest.mock import AsyncMock

import httpx
import pytest

from app.providers.suno.client import SunoClient
from app.providers.suno.client_errors import APIError, AuthFailedError, RateLimitedError
from app.providers.suno.session_auth import SunoSessionAuth


def test_find_audio_url_handles_common_shapes() -> None:
    assert (
        SunoClient.find_audio_url({"clips": [{"audioUrl": "https://cdn.example/a.mp3"}]})
        == "https://cdn.example/a.mp3"
    )
    assert (
        SunoClient.find_audio_url({"data": {"download_url": "https://cdn.example/b.mp3"}})
        == "https://cdn.example/b.mp3"
    )


def test_find_audio_url_returns_none_when_absent() -> None:
    assert SunoClient.find_audio_url({"status": "queued", "clips": [{}]}) is None


@pytest.mark.asyncio
async def test_headers_use_api_key_without_session_auth() -> None:
    client = SunoClient(api_key="token", base_url="https://suno.example")
    try:
        assert await client._headers() == {"Authorization": "Bearer token"}
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_headers_use_session_cookie_and_clerk_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    session.ensure_authenticated.return_value = SunoSessionAuth(
        cookies=[
            {"name": "__client", "value": "client-token"},
            {"name": "suno_device_id", "value": "device-1"},
        ],
        cookie_header="__client=client-token; suno_device_id=device-1",
        client_token="client-token",
        device_id="device-1",
    )
    client = SunoClient(api_key="", base_url="https://studio-api.suno.ai", session_auth=session)
    monkeypatch.setattr(client, "_ensure_clerk_bearer", AsyncMock(return_value="jwt-token"))
    try:
        headers = await client._headers()
    finally:
        await client.close()
    assert headers["Cookie"] == "__client=client-token; suno_device_id=device-1"
    assert headers["Authorization"] == "Bearer jwt-token"
    assert headers["device-id"] == "device-1"
    assert "timestamp" in json.loads(b64decode(headers["browser-token"]).decode("utf-8"))
    session.ensure_authenticated.assert_awaited_once()


def test_extract_clerk_helpers() -> None:
    assert (
        SunoClient._extract_clerk_session_id({"response": {"last_active_session_id": "sess-1"}})
        == "sess-1"
    )
    assert SunoClient._extract_clerk_jwt({"response": {"jwt": "jwt-1"}}) == "jwt-1"


@pytest.mark.asyncio
async def test_get_generation_normalizes_feed_array() -> None:
    client = SunoClient(api_key="token", base_url="https://suno.example")
    client._request = AsyncMock(return_value=[{"id": "clip-1", "status": "complete"}])
    try:
        assert await client.get_generation("clip-1") == {"id": "clip-1", "status": "complete"}
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_get_generation_unwraps_feed_v2_clips() -> None:
    # /api/feed/v2/ returns {"clips": [...]} — unwrap to the single clip dict
    client = SunoClient(api_key="token", base_url="https://suno.example")
    client._request = AsyncMock(
        return_value={
            "clips": [{"id": "clip-1", "status": "complete", "audio_url": "https://cdn/x.mp3"}],
            "num_total_results": 1,
        }
    )
    try:
        out = await client.get_generation("clip-1")
        assert out["status"] == "complete"
        assert out["audio_url"] == "https://cdn/x.mp3"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_get_generation_keeps_sunoapi_task_payload() -> None:
    client = SunoClient(api_key="token", base_url="https://api.sunoapi.org")
    task = {
        "taskId": "task-1",
        "status": "SUCCESS",
        "response": {
            "sunoData": [
                {"id": "audio-1", "audioUrl": "https://cdn.example/audio-1.mp3"},
            ],
        },
    }
    client._request = AsyncMock(return_value=task)
    try:
        assert await client.get_generation("task-1") == task
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_download_headers_omit_auth_for_offhost_cdn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = SunoClient(api_key="secret", base_url="https://studio-api-prod.suno.com")
    monkeypatch.setattr(
        client, "_headers", AsyncMock(return_value={"Authorization": "Bearer secret"})
    )
    try:
        # Off-host CDN → no session credentials leaked.
        assert await client._download_headers("https://audiopipe.suno.ai/x.mp3") == {}
        # Same-origin API path → auth attached.
        assert await client._download_headers("/api/audio/x.mp3") == {
            "Authorization": "Bearer secret"
        }
        # Same-host absolute URL → auth attached.
        assert await client._download_headers("https://studio-api-prod.suno.com/x.mp3") == {
            "Authorization": "Bearer secret"
        }
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_get_account_returns_billing_dict() -> None:
    client = SunoClient(
        api_key="token",
        base_url="https://api.sunoapi.org",
        account_path="/api/v1/generate/credit",
    )
    client._request = AsyncMock(return_value=5)
    try:
        acct = await client.get_account()
        assert acct["credits_left"] == 5
        assert client._request.await_args.args == ("GET", "/api/v1/generate/credit")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_get_account_empty_path_short_circuits() -> None:
    client = SunoClient(api_key="token", base_url="https://suno.example", account_path="")
    client._request = AsyncMock(side_effect=AssertionError("should not be called"))
    try:
        assert await client.get_account() == {}
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_check_captcha_raises_when_required() -> None:
    client = SunoClient(api_key="token", base_url="https://suno.example")
    client._request = AsyncMock(return_value={"required": True})
    try:
        with pytest.raises(AuthFailedError, match="CAPTCHA"):
            await client._check_captcha()
        # posts to the captcha endpoint (older builds wrongly used GET -> 405)
        assert client._request.await_args.args[0] == "POST"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_cancel_generation_requires_configured_endpoint() -> None:
    client = SunoClient(api_key="token", base_url="https://api.sunoapi.org", cancel_path="")
    try:
        with pytest.raises(APIError, match="cancel endpoint"):
            await client.cancel_generation("task-1")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_check_captcha_swallows_endpoint_drift() -> None:
    """A 405/422 from a drifted captcha endpoint must not block generation."""
    client = SunoClient(api_key="token", base_url="https://suno.example")
    client._request = AsyncMock(side_effect=APIError("405: Method not allowed"))
    try:
        await client._check_captcha()  # no raise
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_check_captcha_reraises_auth_failure() -> None:
    client = SunoClient(api_key="token", base_url="https://suno.example")
    client._request = AsyncMock(side_effect=AuthFailedError("auth failed: 401"))
    try:
        with pytest.raises(AuthFailedError):
            await client._check_captcha()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_call_normalizes_path_and_returns_data() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["method"] = request.method
        return httpx.Response(200, json={"code": 200, "msg": "ok", "data": {"taskId": "t"}})

    client = SunoClient(api_key="token", base_url="https://api.sunoapi.org")
    await client._http.aclose()
    client._http = httpx.AsyncClient(
        base_url="https://api.sunoapi.org", transport=httpx.MockTransport(handler)
    )
    try:
        out = await client.api_call("GET", "api/v1/wav/record-info", params={"taskId": "t"})
        assert out == {"taskId": "t"}
        assert seen["method"] == "GET"
        assert seen["url"] == "https://api.sunoapi.org/api/v1/wav/record-info?taskId=t"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_upload_file_targets_upload_host() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"code": 200, "data": {"downloadUrl": "https://cdn/x"}})

    client = SunoClient(
        api_key="token",
        base_url="https://api.sunoapi.org",
        upload_base_url="https://sunoapiorg.redpandaai.co",
    )
    await client._http.aclose()
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        out = await client.upload_file(
            "/api/file-url-upload", json={"fileUrl": "http://x", "uploadPath": "dj"}
        )
        assert out == {"downloadUrl": "https://cdn/x"}
        assert seen["url"] == "https://sunoapiorg.redpandaai.co/api/file-url-upload"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_request_raises_on_sunoapi_error_code() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"code": 429, "msg": "Insufficient credits"},
            request=request,
        )
    )
    client = SunoClient(api_key="token", base_url="https://api.sunoapi.org")
    await client._http.aclose()
    client._http = httpx.AsyncClient(
        base_url="https://api.sunoapi.org",
        transport=transport,
    )
    try:
        with pytest.raises(RateLimitedError, match="429"):
            await client.create_generation({"prompt": "x"})
    finally:
        await client.close()
