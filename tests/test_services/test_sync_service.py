"""Tests for SyncService — push formats trackId:albumId (B3)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.playlist import Playlist
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.services.sync_service import SyncService
from app.ym.models import YMPlaylist


def _make_sync_service(db: AsyncSession, ym_mock: AsyncMock) -> SyncService:
    return SyncService(
        track_repo=TrackRepository(db),
        playlist_repo=PlaylistRepository(db),
        set_repo=SetRepository(db),
        ym=ym_mock,
    )


def _make_ym_mock() -> AsyncMock:
    """Create a mock YM client with default returns."""
    ym = AsyncMock()
    ym.get_playlist = AsyncMock(return_value=YMPlaylist(kind=42, title="Test", revision=1))
    ym.get_playlist_tracks = AsyncMock(return_value=[])
    ym.add_tracks_to_playlist = AsyncMock(return_value={"revision": 2})
    ym.get_tracks = AsyncMock(return_value=[])
    # Default: return IDs unchanged (no album resolution)
    ym.resolve_track_ids_with_albums = AsyncMock(side_effect=lambda ids: ids)
    return ym


# ── B3: _push_to_ym formats trackId:albumId ──────────────


@pytest.mark.asyncio
async def test_push_to_ym_formats_track_album_id(db: AsyncSession) -> None:
    """_push_to_ym should call add_tracks_to_playlist with 'trackId:albumId' format."""
    ym_mock = _make_ym_mock()

    # resolve_track_ids_with_albums returns formatted "trackId:albumId" strings
    ym_mock.resolve_track_ids_with_albums = AsyncMock(return_value=["111:900", "222:901"])

    svc = _make_sync_service(db, ym_mock)

    # Create a playlist with YM link
    pl = Playlist(name="Test PL", platform_ids='{"yandex_music": "42"}')
    db.add(pl)
    await db.flush()

    # Call _push_to_ym directly with local-only track IDs
    on_local_only = {"111", "222"}
    added = await svc._push_to_ym(ym_kind=42, on_local_only=on_local_only)

    assert added == 2

    # Verify add_tracks_to_playlist was called with formatted IDs
    add_call = ym_mock.add_tracks_to_playlist.call_args
    batch = add_call[0][1]  # second positional arg = track IDs

    # Each ID should be in "trackId:albumId" format
    for track_ref in batch:
        assert ":" in track_ref, f"Expected 'trackId:albumId' format, got: {track_ref}"

    # Verify specific formatting
    formatted_set = set(batch)
    assert "111:900" in formatted_set
    assert "222:901" in formatted_set


@pytest.mark.asyncio
async def test_push_to_ym_handles_missing_album_id(db: AsyncSession) -> None:
    """_push_to_ym should handle tracks without album info gracefully."""
    ym_mock = _make_ym_mock()

    # resolve_track_ids_with_albums returns bare ID when album info is unavailable
    ym_mock.resolve_track_ids_with_albums = AsyncMock(return_value=["333"])

    svc = _make_sync_service(db, ym_mock)

    on_local_only = {"333"}
    added = await svc._push_to_ym(ym_kind=42, on_local_only=on_local_only)

    assert added == 1

    # Track without album should still be sent (just without albumId suffix)
    add_call = ym_mock.add_tracks_to_playlist.call_args
    batch = add_call[0][1]
    assert "333" in batch
