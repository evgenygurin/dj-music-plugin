"""YandexClient tests — mocked httpx transport."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.providers.yandex.client import (
    APIError,
    AuthFailedError,
    RateLimitedError,
    YandexClient,
)
from app.providers.yandex.rate_limiter import TokenBucketRateLimiter


@pytest.fixture
def client() -> YandexClient:
    return YandexClient(
        token="test-token",
        user_id="42",
        base_url="https://api.music.yandex.net",
        rate_limiter=TokenBucketRateLimiter(delay_s=0.0),
    )


@pytest.mark.asyncio
@respx.mock
async def test_search_tracks(client: YandexClient) -> None:
    respx.get("https://api.music.yandex.net/search").mock(
        return_value=httpx.Response(
            200,
            json={"result": {"tracks": {"results": [{"id": "1", "title": "A"}], "total": 1}}},
        )
    )
    result = await client.search(query="hello", type="tracks", limit=10)
    assert result["tracks"]["total"] == 1
    assert result["tracks"]["results"][0]["id"] == "1"


@pytest.mark.asyncio
@respx.mock
async def test_401_raises_auth_failed(client: YandexClient) -> None:
    respx.get("https://api.music.yandex.net/tracks").mock(
        return_value=httpx.Response(401, json={"error": "unauthorized"})
    )
    with pytest.raises(AuthFailedError):
        await client.get_tracks(["1"])


@pytest.mark.asyncio
@respx.mock
async def test_429_raises_rate_limited(client: YandexClient) -> None:
    respx.get("https://api.music.yandex.net/tracks").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "5"}, json={"error": "rate"})
    )
    with pytest.raises(RateLimitedError):
        await client.get_tracks(["1"])


@pytest.mark.asyncio
@respx.mock
async def test_get_playlist(client: YandexClient) -> None:
    respx.get("https://api.music.yandex.net/users/42/playlists/3").mock(
        return_value=httpx.Response(
            200, json={"result": {"kind": 3, "title": "P", "revision": 7, "trackCount": 0}}
        )
    )
    pl = await client.get_playlist("42:3")
    assert pl["kind"] == 3
    assert pl["revision"] == 7


@pytest.mark.asyncio
@respx.mock
async def test_modify_playlist_diff(client: YandexClient) -> None:
    respx.post("https://api.music.yandex.net/users/42/playlists/3/change-relative").mock(
        return_value=httpx.Response(200, json={"result": {"revision": 8, "trackCount": 1}})
    )
    diff = [{"op": "insert", "at": 0, "tracks": [{"id": "1", "albumId": "2"}]}]
    result = await client.modify_playlist("42:3", diff=diff, revision=7)
    assert result["revision"] == 8


@pytest.mark.asyncio
@respx.mock
async def test_500_raises_api_error(client: YandexClient) -> None:
    respx.get("https://api.music.yandex.net/tracks").mock(
        return_value=httpx.Response(500, json={"error": "oops"})
    )
    with pytest.raises(APIError):
        await client.get_tracks(["1"])


@pytest.mark.asyncio
@respx.mock
async def test_close_is_idempotent(client: YandexClient) -> None:
    await client.close()
    await client.close()  # must not raise
