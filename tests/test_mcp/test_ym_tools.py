"""Tests for ym_playlists tool — remove_tracks index-based removal (B4)
and ym_get_album empty-response handling (BUG-14)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastmcp.exceptions import ToolError

from app.clients.ym.models import YMAlbum, YMPlaylist, YMTrack

# ── BUG-14: ym_get_album validation ───────────────────


@pytest.mark.asyncio
async def test_ym_get_album_raises_on_empty_stub() -> None:
    """YM returns an empty album dict when the id is unknown — must raise."""
    from app.controllers.tools.yandex.albums import ym_get_album

    ym_mock = AsyncMock()
    ym_mock.get_album = AsyncMock(
        return_value=YMAlbum(
            id="999999",
            title="",
            track_count=None,
            artists=[],
            year=None,
            genre=None,
            tracks=[],
        ),
    )

    from fastmcp.exceptions import NotFoundError as FastMCPNotFoundError

    with pytest.raises(FastMCPNotFoundError, match="Album not found: 999999"):
        await ym_get_album(album_id="999999", include_tracks=True, ym=ym_mock)


@pytest.mark.asyncio
async def test_ym_get_album_returns_album_when_present() -> None:
    """A real album with title or artists must pass through unchanged."""
    from app.controllers.tools.yandex.albums import ym_get_album

    ym_mock = AsyncMock()
    ym_mock.get_album = AsyncMock(
        return_value=YMAlbum(
            id="42",
            title="Real Album",
            track_count=2,
            artists=[{"id": "1", "name": "Artist"}],
            tracks=[YMTrack(id="1", title="A"), YMTrack(id="2", title="B")],
        ),
    )

    result = await ym_get_album(album_id="42", include_tracks=True, ym=ym_mock)
    assert result.album_id == "42"
    assert result.album["title"] == "Real Album"
    assert len(result.album["tracks"]) == 2


@pytest.mark.asyncio
async def test_ym_get_album_rejects_blank_id() -> None:
    """A blank/empty album_id must fail before hitting the YM client."""
    from app.controllers.tools.yandex.albums import ym_get_album

    ym_mock = AsyncMock()
    with pytest.raises(ToolError, match="album_id is required"):
        await ym_get_album(album_id="   ", ym=ym_mock)
    ym_mock.get_album.assert_not_called()


# ── B4: ym_playlists remove_tracks ────────────────────


@pytest.mark.asyncio
async def test_remove_tracks_calls_remove_descending_order() -> None:
    """ym_playlists remove_tracks should remove indices in descending order.

    This prevents index shifting when removing multiple tracks.
    """
    from app.controllers.tools.yandex.playlists import ym_playlists

    ym_mock = AsyncMock()

    # Playlist with 5 tracks
    playlist_tracks = [
        YMTrack(id="100", title="Track 0"),
        YMTrack(id="200", title="Track 1"),
        YMTrack(id="300", title="Track 2"),
        YMTrack(id="200", title="Track 3 (dup ID)"),
        YMTrack(id="400", title="Track 4"),
    ]

    ym_mock.get_playlist = AsyncMock(return_value=YMPlaylist(kind=10, title="My PL", revision=5))
    ym_mock.get_playlist_tracks = AsyncMock(return_value=playlist_tracks)
    ym_mock.remove_tracks_from_playlist = AsyncMock(return_value={"revision": 6})

    # Remove track "200" (appears at indices 1 and 3)
    result = await ym_playlists(
        action="remove_tracks",
        kind=10,
        track_ids=["200"],
        revision=5,
        ym=ym_mock,
    )

    assert result.action == "remove_tracks"
    assert result.removed == 2  # "200" appears twice

    # Verify remove was called in descending index order (3 before 1)
    calls = ym_mock.remove_tracks_from_playlist.call_args_list
    assert len(calls) == 2

    # First call should be index 3 (higher index first)
    first_call_idx = calls[0][0][1]  # second positional arg = from_idx
    second_call_idx = calls[1][0][1]

    assert first_call_idx == 3
    assert second_call_idx == 1


@pytest.mark.asyncio
async def test_remove_tracks_reports_not_found() -> None:
    """ym_playlists remove_tracks should report track IDs not found in playlist."""
    from app.controllers.tools.yandex.playlists import ym_playlists

    ym_mock = AsyncMock()

    playlist_tracks = [
        YMTrack(id="100", title="Track 0"),
        YMTrack(id="200", title="Track 1"),
    ]

    ym_mock.get_playlist = AsyncMock(return_value=YMPlaylist(kind=10, title="My PL", revision=5))
    ym_mock.get_playlist_tracks = AsyncMock(return_value=playlist_tracks)
    ym_mock.remove_tracks_from_playlist = AsyncMock(return_value={"revision": 6})

    result = await ym_playlists(
        action="remove_tracks",
        kind=10,
        track_ids=["200", "999"],  # "999" not in playlist
        revision=5,
        ym=ym_mock,
    )

    assert result.removed == 1
    assert "999" in result.not_found
    assert "200" not in result.not_found


@pytest.mark.asyncio
async def test_remove_tracks_single_track() -> None:
    """ym_playlists remove_tracks should work for a single track removal."""
    from app.controllers.tools.yandex.playlists import ym_playlists

    ym_mock = AsyncMock()

    playlist_tracks = [
        YMTrack(id="100", title="Track A"),
        YMTrack(id="200", title="Track B"),
        YMTrack(id="300", title="Track C"),
    ]

    ym_mock.get_playlist = AsyncMock(return_value=YMPlaylist(kind=10, title="PL", revision=1))
    ym_mock.get_playlist_tracks = AsyncMock(return_value=playlist_tracks)
    ym_mock.remove_tracks_from_playlist = AsyncMock(return_value={"revision": 2})

    result = await ym_playlists(
        action="remove_tracks",
        kind=10,
        track_ids=["200"],
        revision=1,
        ym=ym_mock,
    )

    assert result.removed == 1
    assert result.not_found == []

    # Verify correct index (1) and range (1, 2)
    call_args = ym_mock.remove_tracks_from_playlist.call_args
    assert call_args[0][1] == 1  # from_idx
    assert call_args[0][2] == 2  # to_idx (exclusive)


# ── BUG-018: ym_playlists get_tracks pagination ─────


@pytest.mark.asyncio
async def test_get_tracks_paginates_by_default() -> None:
    """ym_playlists get_tracks must page large playlists to avoid oversized
    responses (BUG-018: 1377-track playlist returned ~106k chars)."""
    from app.controllers.tools.yandex._constants import MAX_PLAYLIST_TRACKS_PAGE
    from app.controllers.tools.yandex.playlists import ym_playlists

    ym_mock = AsyncMock()
    big_playlist = [YMTrack(id=str(i), title=f"Track {i}") for i in range(1377)]
    ym_mock.get_playlist_tracks = AsyncMock(return_value=big_playlist)

    result = await ym_playlists(action="get_tracks", kind=10, ym=ym_mock)

    # Total still reported, but tracks are paged
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

    ym_mock = AsyncMock()
    playlist = [YMTrack(id=str(i), title=f"Track {i}") for i in range(50)]
    ym_mock.get_playlist_tracks = AsyncMock(return_value=playlist)

    result = await ym_playlists(
        action="get_tracks",
        kind=10,
        limit=10,
        offset=20,
        ym=ym_mock,
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
    """The final page must report ``truncated=False`` and ``next_offset=None``."""
    from app.controllers.tools.yandex.playlists import ym_playlists

    ym_mock = AsyncMock()
    playlist = [YMTrack(id=str(i), title=f"Track {i}") for i in range(15)]
    ym_mock.get_playlist_tracks = AsyncMock(return_value=playlist)

    result = await ym_playlists(
        action="get_tracks",
        kind=10,
        limit=10,
        offset=10,
        ym=ym_mock,
    )

    assert result.count == 15
    assert result.offset == 10
    assert len(result.tracks) == 5  # only 5 tracks left
    assert result.truncated is False
    assert result.next_offset is None


@pytest.mark.asyncio
async def test_get_tracks_caps_limit_to_max() -> None:
    """``limit`` larger than ``MAX_PLAYLIST_TRACKS_PAGE`` must be capped."""
    from app.controllers.tools.yandex._constants import MAX_PLAYLIST_TRACKS_PAGE
    from app.controllers.tools.yandex.playlists import ym_playlists

    ym_mock = AsyncMock()
    playlist = [YMTrack(id=str(i), title=f"Track {i}") for i in range(1000)]
    ym_mock.get_playlist_tracks = AsyncMock(return_value=playlist)

    result = await ym_playlists(
        action="get_tracks",
        kind=10,
        limit=10_000,  # absurdly large
        ym=ym_mock,
    )

    assert result.limit == MAX_PLAYLIST_TRACKS_PAGE
    assert len(result.tracks) == MAX_PLAYLIST_TRACKS_PAGE


@pytest.mark.asyncio
async def test_get_tracks_rejects_negative_offset() -> None:
    """A negative ``offset`` must raise instead of returning the tail."""
    from app.controllers.tools.yandex.playlists import ym_playlists

    ym_mock = AsyncMock()
    ym_mock.get_playlist_tracks = AsyncMock(return_value=[YMTrack(id="1", title="A")])

    with pytest.raises(ToolError, match="offset must be >= 0"):
        await ym_playlists(
            action="get_tracks",
            kind=10,
            offset=-1,
            ym=ym_mock,
        )
