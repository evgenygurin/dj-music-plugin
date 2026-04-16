"""Tests for platform tools — playlists and album retrieval."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastmcp.exceptions import ToolError

from app.core.constants import Provider
from app.providers.models import ProviderAlbum, ProviderArtist, ProviderPlaylist, ProviderTrack

# ── BUG-14: get_platform_album validation ─────────────


@pytest.mark.asyncio
async def test_get_platform_album_raises_on_empty_stub() -> None:
    """YM returns an empty album dict when the id is unknown — must raise."""
    from app.controllers.tools.platform.albums import get_platform_album

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
        await get_platform_album(album_id="999999", include_tracks=True, provider=provider_mock)


@pytest.mark.asyncio
async def test_get_platform_album_returns_album_when_present() -> None:
    """A real album with title or artists must pass through unchanged."""
    from app.controllers.tools.platform.albums import get_platform_album

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

    result = await get_platform_album(album_id="42", include_tracks=True, provider=provider_mock)
    assert result.album_id == "42"
    assert result.album["title"] == "Real Album"
    assert len(result.album["tracks"]) == 2


@pytest.mark.asyncio
async def test_get_platform_album_rejects_blank_id() -> None:
    """A blank/empty album_id must fail before hitting the provider."""
    from app.controllers.tools.platform.albums import get_platform_album

    provider_mock = AsyncMock()
    with pytest.raises(ToolError, match="album_id is required"):
        await get_platform_album(album_id="   ", provider=provider_mock)
    provider_mock.get_album.assert_not_called()


# ── B4: platform_playlists remove_tracks ──────────────


@pytest.mark.asyncio
async def test_remove_tracks_calls_provider_once() -> None:
    """platform_playlists remove_tracks delegates directly to provider.remove_tracks_from_playlist."""
    from app.controllers.tools.platform.playlists import platform_playlists

    provider_mock = AsyncMock()
    provider_mock.remove_tracks_from_playlist = AsyncMock(return_value=None)

    result = await platform_playlists(
        action="remove_tracks",
        playlist_id="10",
        track_ids=["200"],
        provider=provider_mock,
    )

    assert result.action == "remove_tracks"
    assert result.removed == 1
    provider_mock.remove_tracks_from_playlist.assert_called_once_with("10", ["200"])


@pytest.mark.asyncio
async def test_remove_tracks_multiple_ids() -> None:
    """remove_tracks passes all requested IDs to provider in one call."""
    from app.controllers.tools.platform.playlists import platform_playlists

    provider_mock = AsyncMock()
    provider_mock.remove_tracks_from_playlist = AsyncMock(return_value=None)

    result = await platform_playlists(
        action="remove_tracks",
        playlist_id="10",
        track_ids=["200", "999"],
        provider=provider_mock,
    )

    assert result.removed == 2
    provider_mock.remove_tracks_from_playlist.assert_called_once()


@pytest.mark.asyncio
async def test_remove_tracks_single_track() -> None:
    """platform_playlists remove_tracks works for a single track removal."""
    from app.controllers.tools.platform.playlists import platform_playlists

    provider_mock = AsyncMock()
    provider_mock.remove_tracks_from_playlist = AsyncMock(return_value=None)

    result = await platform_playlists(
        action="remove_tracks",
        playlist_id="10",
        track_ids=["200"],
        provider=provider_mock,
    )

    assert result.removed == 1
    provider_mock.remove_tracks_from_playlist.assert_called_once()


# ── BUG-018: platform_playlists get_tracks pagination ─


@pytest.mark.asyncio
async def test_get_tracks_paginates_by_default() -> None:
    """platform_playlists get_tracks must page large playlists to avoid oversized responses."""
    from app.controllers.tools.platform._constants import MAX_PLAYLIST_TRACKS_PAGE
    from app.controllers.tools.platform.playlists import platform_playlists

    provider_mock = AsyncMock()
    big_playlist = [
        ProviderTrack(id=str(i), title=f"Track {i}", provider=Provider.YANDEX_MUSIC)
        for i in range(1377)
    ]
    provider_mock.get_playlist_tracks = AsyncMock(return_value=big_playlist)

    result = await platform_playlists(
        action="get_tracks", playlist_id="10", provider=provider_mock
    )

    assert result.count == 1377
    assert result.limit == MAX_PLAYLIST_TRACKS_PAGE
    assert result.offset == 0
    assert len(result.tracks) == MAX_PLAYLIST_TRACKS_PAGE
    assert len(result.track_ids) == MAX_PLAYLIST_TRACKS_PAGE
    assert result.truncated is True
    assert result.next_offset == MAX_PLAYLIST_TRACKS_PAGE


@pytest.mark.asyncio
async def test_list_playlists_paginates_by_default() -> None:
    """platform_playlists list must paginate to avoid oversized structured output."""
    from app.controllers.tools.platform.playlists import DEFAULT_PLAYLISTS_PAGE, platform_playlists

    provider_mock = AsyncMock()
    many_playlists = [
        ProviderPlaylist(
            id=f"uid:{i}",
            owner_id="uid",
            title=f"Playlist {i}",
            track_count=i,
            provider=Provider.YANDEX_MUSIC,
        )
        for i in range(1377)
    ]
    provider_mock.list_user_playlists = AsyncMock(return_value=many_playlists)

    result = await platform_playlists(action="list", provider=provider_mock)

    assert result.action == "list"
    assert result.count == 1377
    assert result.offset == 0
    assert result.limit == DEFAULT_PLAYLISTS_PAGE
    assert result.playlists is not None
    assert len(result.playlists) == DEFAULT_PLAYLISTS_PAGE
    assert result.truncated is True
    assert result.next_offset == DEFAULT_PLAYLISTS_PAGE


@pytest.mark.asyncio
async def test_get_tracks_respects_limit_and_offset() -> None:
    """get_tracks must accept limit/offset and slice the playlist accordingly."""
    from app.controllers.tools.platform.playlists import platform_playlists

    provider_mock = AsyncMock()
    playlist = [
        ProviderTrack(id=str(i), title=f"Track {i}", provider=Provider.YANDEX_MUSIC)
        for i in range(50)
    ]
    provider_mock.get_playlist_tracks = AsyncMock(return_value=playlist)

    result = await platform_playlists(
        action="get_tracks",
        playlist_id="10",
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
    from app.controllers.tools.platform.playlists import platform_playlists

    provider_mock = AsyncMock()
    playlist = [
        ProviderTrack(id=str(i), title=f"Track {i}", provider=Provider.YANDEX_MUSIC)
        for i in range(15)
    ]
    provider_mock.get_playlist_tracks = AsyncMock(return_value=playlist)

    result = await platform_playlists(
        action="get_tracks",
        playlist_id="10",
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
    from app.controllers.tools.platform._constants import MAX_PLAYLIST_TRACKS_PAGE
    from app.controllers.tools.platform.playlists import platform_playlists

    provider_mock = AsyncMock()
    playlist = [
        ProviderTrack(id=str(i), title=f"Track {i}", provider=Provider.YANDEX_MUSIC)
        for i in range(1000)
    ]
    provider_mock.get_playlist_tracks = AsyncMock(return_value=playlist)

    result = await platform_playlists(
        action="get_tracks",
        playlist_id="10",
        limit=10_000,
        provider=provider_mock,
    )

    assert result.limit == MAX_PLAYLIST_TRACKS_PAGE
    assert len(result.tracks) == MAX_PLAYLIST_TRACKS_PAGE


@pytest.mark.asyncio
async def test_get_tracks_rejects_negative_offset() -> None:
    """A negative offset must raise instead of returning the tail."""
    from app.controllers.tools.platform.playlists import platform_playlists

    provider_mock = AsyncMock()
    provider_mock.get_playlist_tracks = AsyncMock(
        return_value=[ProviderTrack(id="1", title="A", provider=Provider.YANDEX_MUSIC)]
    )

    with pytest.raises(ToolError, match="offset must be >= 0"):
        await platform_playlists(
            action="get_tracks",
            playlist_id="10",
            offset=-1,
            provider=provider_mock,
        )


@pytest.mark.asyncio
async def test_resolve_platform_track_ids_returns_ordered_mapping() -> None:
    """resolve_platform_track_ids maps local IDs via repository without search fallback."""
    from app.controllers.tools.platform.tracks import resolve_platform_track_ids

    repo_mock = AsyncMock()
    repo_mock.resolve_local_ids_to_platform = AsyncMock(
        return_value={101: "ym:abc", 303: "ym:xyz"}
    )

    result = await resolve_platform_track_ids(
        track_ids=[101, 202, 303],
        platform="yandex_music",
        strict=False,
        track_repo=repo_mock,
    )

    assert result.requested == 3
    assert result.resolved == 2
    assert result.unresolved_track_ids == [202]
    assert [item.local_track_id for item in result.mappings] == [101, 202, 303]
    assert [item.platform_track_id for item in result.mappings] == ["ym:abc", None, "ym:xyz"]
    repo_mock.resolve_local_ids_to_platform.assert_awaited_once_with(
        [101, 202, 303], platform="yandex_music"
    )


@pytest.mark.asyncio
async def test_resolve_platform_track_ids_strict_rejects_unmapped() -> None:
    """strict=true should fail if at least one local track has no external mapping."""
    from app.controllers.tools.platform.tracks import resolve_platform_track_ids

    repo_mock = AsyncMock()
    repo_mock.resolve_local_ids_to_platform = AsyncMock(return_value={101: "ym:abc"})

    with pytest.raises(ToolError, match="Missing yandex_music mapping"):
        await resolve_platform_track_ids(
            track_ids=[101, 202],
            platform="yandex_music",
            strict=True,
            track_repo=repo_mock,
        )
