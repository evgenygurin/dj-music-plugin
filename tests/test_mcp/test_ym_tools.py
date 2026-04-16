"""Tests for ym_playlists tool and ym_get_album — using MusicProvider interface."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastmcp.exceptions import ToolError

from app.config import settings
from app.core.constants import Provider
from app.providers.models import ProviderAlbum, ProviderArtist, ProviderTrack

# ── BUG-14: ym_get_album validation ───────────────────


@pytest.mark.asyncio
async def test_ym_get_album_raises_on_empty_stub() -> None:
    """YM returns an empty album dict when the id is unknown — must raise."""
    from app.controllers.tools.yandex.albums import ym_get_album

    provider_mock = AsyncMock()
    provider_mock.get_album = AsyncMock(
        return_value=ProviderAlbum(
            id="999999",
            title="",
            track_count=None,
            artists=[],
            tracks=[],
            provider=Provider.YANDEX_MUSIC,
        ),
    )

    from fastmcp.exceptions import NotFoundError as FastMCPNotFoundError

    with pytest.raises(FastMCPNotFoundError, match="Album not found: 999999"):
        await ym_get_album(album_id="999999", include_tracks=True, provider=provider_mock)


@pytest.mark.asyncio
async def test_ym_get_album_returns_album_when_present() -> None:
    """A real album with title or artists must pass through unchanged."""
    from app.controllers.tools.yandex.albums import ym_get_album

    provider_mock = AsyncMock()
    provider_mock.get_album = AsyncMock(
        return_value=ProviderAlbum(
            id="42",
            title="Real Album",
            track_count=2,
            artists=[ProviderArtist(id="1", name="Artist", provider=Provider.YANDEX_MUSIC)],
            tracks=[
                ProviderTrack(id="1", title="A", provider=Provider.YANDEX_MUSIC),
                ProviderTrack(id="2", title="B", provider=Provider.YANDEX_MUSIC),
            ],
            provider=Provider.YANDEX_MUSIC,
        ),
    )

    result = await ym_get_album(album_id="42", include_tracks=True, provider=provider_mock)
    assert result.album_id == "42"
    assert result.album["title"] == "Real Album"
    assert len(result.album["tracks"]) == 2


@pytest.mark.asyncio
async def test_ym_get_album_rejects_blank_id() -> None:
    """A blank/empty album_id must fail before hitting the provider."""
    from app.controllers.tools.yandex.albums import ym_get_album

    provider_mock = AsyncMock()
    with pytest.raises(ToolError, match="album_id is required"):
        await ym_get_album(album_id="   ", provider=provider_mock)
    provider_mock.get_album.assert_not_called()


# ── B4: ym_playlists remove_tracks ────────────────────


@pytest.mark.asyncio
async def test_remove_tracks_calls_provider_once() -> None:
    """ym_playlists remove_tracks delegates directly to provider.remove_tracks_from_playlist."""
    from app.controllers.tools.yandex.playlists import ym_playlists

    provider_mock = AsyncMock()
    provider_mock.remove_tracks_from_playlist = AsyncMock(return_value=None)

    result = await ym_playlists(
        action="remove_tracks",
        kind=10,
        track_ids=["200"],
        provider=provider_mock,
    )

    assert result.action == "remove_tracks"
    assert result.removed == 1
    playlist_id = f"{settings.ym_user_id}:10"
    provider_mock.remove_tracks_from_playlist.assert_called_once_with(playlist_id, ["200"])


@pytest.mark.asyncio
async def test_remove_tracks_multiple_ids() -> None:
    """remove_tracks passes all requested IDs to provider in one call."""
    from app.controllers.tools.yandex.playlists import ym_playlists

    provider_mock = AsyncMock()
    provider_mock.remove_tracks_from_playlist = AsyncMock(return_value=None)

    result = await ym_playlists(
        action="remove_tracks",
        kind=10,
        track_ids=["200", "999"],
        provider=provider_mock,
    )

    assert result.removed == 2
    provider_mock.remove_tracks_from_playlist.assert_called_once()


@pytest.mark.asyncio
async def test_remove_tracks_single_track() -> None:
    """ym_playlists remove_tracks works for a single track removal."""
    from app.controllers.tools.yandex.playlists import ym_playlists

    provider_mock = AsyncMock()
    provider_mock.remove_tracks_from_playlist = AsyncMock(return_value=None)

    result = await ym_playlists(
        action="remove_tracks",
        kind=10,
        track_ids=["200"],
        provider=provider_mock,
    )

    assert result.removed == 1
    provider_mock.remove_tracks_from_playlist.assert_called_once()


# ── BUG-018: ym_playlists get_tracks pagination ─────


@pytest.mark.asyncio
async def test_get_tracks_paginates_by_default() -> None:
    """ym_playlists get_tracks must page large playlists to avoid oversized responses."""
    from app.controllers.tools.yandex._constants import MAX_PLAYLIST_TRACKS_PAGE
    from app.controllers.tools.yandex.playlists import ym_playlists

    provider_mock = AsyncMock()
    big_playlist = [
        ProviderTrack(id=str(i), title=f"Track {i}", provider=Provider.YANDEX_MUSIC)
        for i in range(1377)
    ]
    provider_mock.get_playlist_tracks = AsyncMock(return_value=big_playlist)

    result = await ym_playlists(action="get_tracks", kind=10, provider=provider_mock)

    assert result.count == 1377
    assert result.limit == MAX_PLAYLIST_TRACKS_PAGE
    assert result.offset == 0
    assert len(result.tracks) == MAX_PLAYLIST_TRACKS_PAGE
    assert len(result.track_ids) == MAX_PLAYLIST_TRACKS_PAGE
    assert result.truncated is True
    assert result.next_offset == MAX_PLAYLIST_TRACKS_PAGE


@pytest.mark.asyncio
async def test_get_tracks_respects_limit_and_offset() -> None:
    """get_tracks must accept limit/offset and slice the playlist accordingly."""
    from app.controllers.tools.yandex.playlists import ym_playlists

    provider_mock = AsyncMock()
    playlist = [
        ProviderTrack(id=str(i), title=f"Track {i}", provider=Provider.YANDEX_MUSIC)
        for i in range(50)
    ]
    provider_mock.get_playlist_tracks = AsyncMock(return_value=playlist)

    result = await ym_playlists(
        action="get_tracks",
        kind=10,
        limit=10,
        offset=20,
        provider=provider_mock,
    )

    assert result.count == 50
    assert result.offset == 20
    assert result.limit == 10
    assert result.track_ids == [str(i) for i in range(20, 30)]
    assert len(result.tracks) == 10
    assert result.truncated is True
    assert result.next_offset == 30


@pytest.mark.asyncio
async def test_get_tracks_last_page_marks_not_truncated() -> None:
    """The final page must report truncated=False and next_offset=None."""
    from app.controllers.tools.yandex.playlists import ym_playlists

    provider_mock = AsyncMock()
    playlist = [
        ProviderTrack(id=str(i), title=f"Track {i}", provider=Provider.YANDEX_MUSIC)
        for i in range(15)
    ]
    provider_mock.get_playlist_tracks = AsyncMock(return_value=playlist)

    result = await ym_playlists(
        action="get_tracks",
        kind=10,
        limit=10,
        offset=10,
        provider=provider_mock,
    )

    assert result.count == 15
    assert result.offset == 10
    assert len(result.tracks) == 5
    assert result.truncated is False
    assert result.next_offset is None


@pytest.mark.asyncio
async def test_get_tracks_caps_limit_to_max() -> None:
    """limit larger than MAX_PLAYLIST_TRACKS_PAGE must be capped."""
    from app.controllers.tools.yandex._constants import MAX_PLAYLIST_TRACKS_PAGE
    from app.controllers.tools.yandex.playlists import ym_playlists

    provider_mock = AsyncMock()
    playlist = [
        ProviderTrack(id=str(i), title=f"Track {i}", provider=Provider.YANDEX_MUSIC)
        for i in range(1000)
    ]
    provider_mock.get_playlist_tracks = AsyncMock(return_value=playlist)

    result = await ym_playlists(
        action="get_tracks",
        kind=10,
        limit=10_000,
        provider=provider_mock,
    )

    assert result.limit == MAX_PLAYLIST_TRACKS_PAGE
    assert len(result.tracks) == MAX_PLAYLIST_TRACKS_PAGE


@pytest.mark.asyncio
async def test_get_tracks_rejects_negative_offset() -> None:
    """A negative offset must raise instead of returning the tail."""
    from app.controllers.tools.yandex.playlists import ym_playlists

    provider_mock = AsyncMock()
    provider_mock.get_playlist_tracks = AsyncMock(
        return_value=[ProviderTrack(id="1", title="A", provider=Provider.YANDEX_MUSIC)]
    )

    with pytest.raises(ToolError, match="offset must be >= 0"):
        await ym_playlists(
            action="get_tracks",
            kind=10,
            offset=-1,
            provider=provider_mock,
        )
