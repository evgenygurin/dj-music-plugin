"""Tests for SyncService._push_to_ym via MusicProvider interface."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models.playlist import Playlist
from app.db.repositories.playlist import PlaylistRepository
from app.db.repositories.set import SetRepository
from app.db.repositories.track import TrackRepository
from app.services.sync_service import SyncService


def _make_sync_service(db: AsyncSession, provider_mock: AsyncMock) -> SyncService:
    return SyncService(
        track_repo=TrackRepository(db),
        playlist_repo=PlaylistRepository(db),
        set_repo=SetRepository(db),
        ym=provider_mock,
    )


def _make_provider_mock() -> AsyncMock:
    """Create a mock MusicProvider with default returns."""
    provider = AsyncMock()
    provider.get_playlist = AsyncMock(return_value=None)
    provider.get_playlist_tracks = AsyncMock(return_value=[])
    provider.add_tracks_to_playlist = AsyncMock(return_value=None)
    provider.get_tracks = AsyncMock(return_value=[])
    return provider


# ── _push_to_ym delegates to MusicProvider ──────────────


@pytest.mark.asyncio
async def test_push_to_ym_calls_provider_with_playlist_id(db: AsyncSession) -> None:
    """_push_to_ym calls add_tracks_to_playlist with owner_id:kind playlist ID."""
    provider_mock = _make_provider_mock()
    svc = _make_sync_service(db, provider_mock)

    pl = Playlist(name="Test PL", platform_ids='{"yandex_music": "42"}')
    db.add(pl)
    await db.flush()

    on_local_only = {"111", "222"}
    added = await svc._push_to_ym(ym_kind=42, on_local_only=on_local_only)

    assert added == 2

    add_call = provider_mock.add_tracks_to_playlist.call_args
    playlist_id = add_call[0][0]  # first positional arg = playlist_id
    batch = add_call[0][1]  # second positional arg = track IDs

    assert playlist_id == f"{settings.ym_user_id}:42"
    assert set(batch) == {"111", "222"}


@pytest.mark.asyncio
async def test_push_to_ym_handles_missing_album_id(db: AsyncSession) -> None:
    """_push_to_ym passes bare IDs to provider when album info is unavailable."""
    provider_mock = _make_provider_mock()
    svc = _make_sync_service(db, provider_mock)

    on_local_only = {"333"}
    added = await svc._push_to_ym(ym_kind=42, on_local_only=on_local_only)

    assert added == 1

    add_call = provider_mock.add_tracks_to_playlist.call_args
    batch = add_call[0][1]
    assert "333" in batch
