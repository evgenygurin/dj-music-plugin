"""YandexAdapter tests — asserts Provider protocol conformance."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.providers.yandex.adapter import YandexAdapter
from app.registry.provider import Provider


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client.search.return_value = {"tracks": {"results": [{"id": "1", "title": "X"}], "total": 1}}
    client.get_tracks.return_value = [{"id": "1", "title": "X", "durationMs": 200000}]
    client.get_similar.return_value = [{"id": "2", "title": "Y"}]
    client.get_playlist.return_value = {"kind": 3, "title": "P", "revision": 7, "trackCount": 0}
    client.modify_playlist.return_value = {"revision": 8}
    client.get_liked_ids.return_value = ["1", "2", "3"]
    client.download_track.return_value = Path("/tmp/x.mp3")
    return client


def test_adapter_satisfies_protocol(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    assert isinstance(adapter, Provider)
    assert adapter.name == "yandex"


@pytest.mark.asyncio
async def test_read_tracks(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    result = await adapter.read("track", id="1", params={})
    assert result["id"] == "1"
    assert result["title"] == "X"
    mock_client.get_tracks.assert_awaited_once_with(["1"])


@pytest.mark.asyncio
async def test_read_similar(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    result = await adapter.read("track_similar", id="1", params={})
    assert result["results"][0]["id"] == "2"


@pytest.mark.asyncio
async def test_read_playlist(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    result = await adapter.read("playlist", id="42:3", params={})
    assert result["revision"] == 7


@pytest.mark.asyncio
async def test_read_unknown_entity_raises(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    with pytest.raises(ValueError, match="unknown"):
        await adapter.read("bogus", id="1", params={})


@pytest.mark.asyncio
async def test_write_playlist_add_tracks(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    result = await adapter.write(
        "playlist",
        operation="add_tracks",
        params={"playlist_id": "42:3", "track_ids": ["1", "2"], "revision": 7},
    )
    assert result["revision"] == 8


@pytest.mark.asyncio
async def test_write_playlist_remove_tracks(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    mock_client.modify_playlist.return_value = {"revision": 9}
    result = await adapter.write(
        "playlist",
        operation="remove_tracks",
        params={"playlist_id": "42:3", "from": 0, "to": 1, "revision": 8},
    )
    assert result["revision"] == 9


@pytest.mark.asyncio
async def test_write_likes_add(mock_client: AsyncMock) -> None:
    mock_client.add_likes.return_value = {"ok": True}
    adapter = YandexAdapter(client=mock_client)
    result = await adapter.write("likes", operation="add", params={"track_ids": ["1", "2"]})
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_search_delegates_to_client(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    result = await adapter.search("hello", type="tracks", limit=10)
    assert result["tracks"]["total"] == 1


@pytest.mark.asyncio
async def test_download_audio_returns_path(mock_client: AsyncMock, tmp_path: Path) -> None:
    target = tmp_path / "1.mp3"
    mock_client.download_track.return_value = target
    adapter = YandexAdapter(client=mock_client, download_dir=tmp_path)
    result = await adapter.download_audio("1")
    assert result == target


@pytest.mark.asyncio
async def test_close_calls_client(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    await adapter.close()
    mock_client.close.assert_awaited_once()
