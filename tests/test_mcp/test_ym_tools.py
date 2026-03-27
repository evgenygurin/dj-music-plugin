"""Tests for ym_playlists tool — remove_tracks index-based removal (B4)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.ym.models import YMPlaylist, YMTrack

# ── B4: ym_playlists remove_tracks ────────────────────


@pytest.mark.asyncio
async def test_remove_tracks_calls_remove_descending_order() -> None:
    """ym_playlists remove_tracks should remove indices in descending order.

    This prevents index shifting when removing multiple tracks.
    """
    from app.mcp.tools.ym import ym_playlists

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
        ctx=None,
    )

    assert result["action"] == "remove_tracks"
    assert result["removed"] == 2  # "200" appears twice

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
    from app.mcp.tools.ym import ym_playlists

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
        ctx=None,
    )

    assert result["removed"] == 1
    assert "999" in result["not_found"]
    assert "200" not in result["not_found"]


@pytest.mark.asyncio
async def test_remove_tracks_single_track() -> None:
    """ym_playlists remove_tracks should work for a single track removal."""
    from app.mcp.tools.ym import ym_playlists

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
        ctx=None,
    )

    assert result["removed"] == 1
    assert result["not_found"] == []

    # Verify correct index (1) and range (1, 2)
    call_args = ym_mock.remove_tracks_from_playlist.call_args
    assert call_args[0][1] == 1  # from_idx
    assert call_args[0][2] == 2  # to_idx (exclusive)
