"""Tests for YandexMusicClient using httpx.MockTransport."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.core.errors import APIError, AuthFailedError, RateLimitedError
from app.ym.client import YandexMusicClient
from app.ym.rate_limiter import RateLimiter


def _make_client(
    handler: Any,
    user_id: str = "123",
) -> YandexMusicClient:
    """Create a YandexMusicClient with mocked transport (no delays)."""
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        transport=transport,
        base_url="https://api.music.yandex.net",
    )
    ym = YandexMusicClient.__new__(YandexMusicClient)
    ym._client = client
    ym._token = "test-token"
    ym._user_id = user_id
    ym._rate_limiter = RateLimiter(delay=0, max_retries=2, backoff_factor=0.01)
    return ym


def _json_response(data: dict[str, Any], status: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json=data,
    )


# ── test_search_tracks ────────────────────────────────────


@pytest.mark.asyncio
async def test_search_tracks() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/search" in str(request.url)
        return _json_response(
            {
                "result": {
                    "tracks": {
                        "results": [
                            {
                                "id": 111,
                                "title": "Acid Rain",
                                "durationMs": 360000,
                                "artists": [{"id": 1, "name": "Recondite"}],
                                "albums": [{"id": 10, "title": "On Acid"}],
                                "coverUri": "cover/%%",
                                "explicit": False,
                            },
                        ],
                        "total": 1,
                    },
                    "albums": {"results": [], "total": 0},
                    "artists": {"results": [], "total": 0},
                    "playlists": {"results": [], "total": 0},
                },
            },
        )

    ym = _make_client(handler)
    result = await ym.search("Acid Rain", type="all", limit=5)

    assert len(result.tracks) == 1
    assert result.tracks[0].id == "111"
    assert result.tracks[0].title == "Acid Rain"
    assert result.tracks[0].duration_ms == 360000
    assert len(result.albums) == 0
    await ym.close()


# ── test_get_tracks_batch ─────────────────────────────────


@pytest.mark.asyncio
async def test_get_tracks_batch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "trackIds" in str(request.url)
        return _json_response(
            {
                "result": [
                    {"id": 1, "title": "Track A", "durationMs": 240000},
                    {"id": 2, "title": "Track B", "durationMs": 300000},
                ],
            },
        )

    ym = _make_client(handler)
    tracks = await ym.get_tracks(["1", "2"])

    assert len(tracks) == 2
    assert tracks[0].id == "1"
    assert tracks[0].title == "Track A"
    assert tracks[1].id == "2"
    await ym.close()


# ── test_get_album ────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_album() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            {
                "result": {
                    "id": 555,
                    "title": "Fabric 98",
                    "trackCount": 22,
                    "artists": [{"id": 3, "name": "Various"}],
                    "year": 2018,
                    "genre": "techno",
                },
            },
        )

    ym = _make_client(handler)
    album = await ym.get_album("555")

    assert album.id == "555"
    assert album.title == "Fabric 98"
    assert album.track_count == 22
    assert album.genre == "techno"
    assert album.tracks == []  # regular endpoint → no tracks
    await ym.close()


@pytest.mark.asyncio
async def test_get_album_with_tracks_flattens_volumes() -> None:
    """YM /albums/{id}/with-tracks returns volumes: list[list[track]] — we flatten."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/with-tracks" in str(request.url)
        return _json_response(
            {
                "result": {
                    "id": 777,
                    "title": "Double LP",
                    "trackCount": 3,
                    "artists": [{"id": 9, "name": "Artist"}],
                    "volumes": [
                        [
                            {"id": 1, "title": "Intro", "durationMs": 120000},
                            {"id": 2, "title": "Peak", "durationMs": 360000},
                        ],
                        [
                            {"id": 3, "title": "Outro", "durationMs": 240000},
                        ],
                    ],
                },
            },
        )

    ym = _make_client(handler)
    album = await ym.get_album("777", with_tracks=True)

    assert album.id == "777"
    assert len(album.tracks) == 3
    assert [t.id for t in album.tracks] == ["1", "2", "3"]
    assert [t.title for t in album.tracks] == ["Intro", "Peak", "Outro"]
    await ym.close()


# ── test_list_user_playlists ──────────────────────────────


@pytest.mark.asyncio
async def test_list_user_playlists() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/users/123/playlists/list" in str(request.url)
        return _json_response(
            {
                "result": [
                    {
                        "kind": 3,
                        "owner": {"uid": 123},
                        "title": "DJ Set 001",
                        "trackCount": 15,
                        "visibility": "private",
                        "revision": 7,
                    },
                    {
                        "kind": 5,
                        "owner": {"uid": 123},
                        "title": "DJ Set 002",
                        "trackCount": 20,
                        "visibility": "public",
                        "revision": 2,
                    },
                ],
            },
        )

    ym = _make_client(handler)
    playlists = await ym.list_user_playlists()

    assert len(playlists) == 2
    assert playlists[0].kind == 3
    assert playlists[0].title == "DJ Set 001"
    assert playlists[0].revision == 7
    assert playlists[1].visibility == "public"
    await ym.close()


# ── test_rate_limited_retries ─────────────────────────────


@pytest.mark.asyncio
async def test_rate_limited_retries() -> None:
    """First request returns 429, second returns 200 — should succeed."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(status_code=429, text="Too Many Requests")
        return _json_response(
            {"result": [{"id": 99, "title": "Recovered", "durationMs": 180000}]},
        )

    ym = _make_client(handler)
    tracks = await ym.get_tracks(["99"])

    assert call_count == 2
    assert len(tracks) == 1
    assert tracks[0].title == "Recovered"
    await ym.close()


@pytest.mark.asyncio
async def test_rate_limited_exhausted() -> None:
    """All retries return 429 — should raise RateLimitedError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=429, text="Too Many Requests")

    ym = _make_client(handler)
    with pytest.raises(RateLimitedError):
        await ym.get_tracks(["1"])
    await ym.close()


# ── test_auth_failed ──────────────────────────────────────


@pytest.mark.asyncio
async def test_auth_failed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=401, text="Unauthorized")

    ym = _make_client(handler)
    with pytest.raises(AuthFailedError):
        await ym.search("anything")
    await ym.close()


@pytest.mark.asyncio
async def test_auth_failed_403() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=403, text="Forbidden")

    ym = _make_client(handler)
    with pytest.raises(APIError) as exc_info:
        await ym.get_tracks(["1"])
    assert exc_info.value.status_code == 403
    await ym.close()


# ── test_get_similar ──────────────────────────────────────


@pytest.mark.asyncio
async def test_get_similar() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            {
                "result": {
                    "similarTracks": [
                        {"id": 42, "title": "Similar One", "durationMs": 420000},
                    ],
                },
            },
        )

    ym = _make_client(handler)
    similar = await ym.get_similar("10")

    assert len(similar) == 1
    assert similar[0].id == "42"
    assert similar[0].title == "Similar One"
    await ym.close()


# ── test_create_playlist ──────────────────────────────────


@pytest.mark.asyncio
async def test_create_playlist() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/users/123/playlists/create" in str(request.url)
        return _json_response(
            {
                "result": {
                    "kind": 10,
                    "owner": {"uid": 123},
                    "title": "New Set",
                    "trackCount": 0,
                    "visibility": "private",
                    "revision": 1,
                },
            },
        )

    ym = _make_client(handler)
    pl = await ym.create_playlist("New Set", visibility="private")

    assert pl.kind == 10
    assert pl.title == "New Set"
    assert pl.revision == 1
    await ym.close()


# ── test_add_tracks_to_playlist ───────────────────────────


@pytest.mark.asyncio
async def test_add_tracks_to_playlist() -> None:
    captured_body: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/change-relative" in str(request.url)
        # httpx sends form data — parse it
        body = request.content.decode()
        for part in body.split("&"):
            k, v = part.split("=", 1)
            captured_body[k] = v
        return _json_response({"result": {"kind": 3, "revision": 8}})

    ym = _make_client(handler)
    result = await ym.add_tracks_to_playlist(
        kind=3,
        track_ids=["100", "200"],
        revision=7,
    )

    assert result.get("kind") == 3
    assert "diff" in captured_body
    await ym.close()
