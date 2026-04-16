"""Tests for SyncService._push_to_platform via MusicProvider interface."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import Provider
from app.db.repositories.playlist import PlaylistRepository
from app.db.repositories.set import SetRepository
from app.db.repositories.track import TrackRepository
from app.services.sync_service import SyncService


def _make_sync_service(db: AsyncSession, provider_mock: AsyncMock) -> SyncService:
    return SyncService(
        track_repo=TrackRepository(db),
        playlist_repo=PlaylistRepository(db),
        set_repo=SetRepository(db),
        provider=provider_mock,
    )


def _make_provider_mock() -> AsyncMock:
    """Create a mock MusicProvider with default returns."""
    provider = AsyncMock()
    provider.provider = Provider.YANDEX_MUSIC
    provider.get_playlist = AsyncMock(return_value=None)
    provider.get_playlist_tracks = AsyncMock(return_value=[])
    provider.add_tracks_to_playlist = AsyncMock(return_value=None)
    provider.get_tracks = AsyncMock(return_value=[])
    return provider


# ── _push_to_platform delegates to MusicProvider ──────────────


@pytest.mark.asyncio
async def test_push_to_platform_calls_provider_with_playlist_id(db: AsyncSession) -> None:
    """_push_to_platform calls add_tracks_to_playlist with the given platform_playlist_id."""
    provider_mock = _make_provider_mock()
    svc = _make_sync_service(db, provider_mock)

    on_local_only = {"111", "222"}
    platform_playlist_id = "12345678:42"
    added = await svc._push_to_platform(
        platform_playlist_id=platform_playlist_id,
        on_local_only=on_local_only,
    )

    assert added == 2

    add_call = provider_mock.add_tracks_to_playlist.call_args
    called_playlist_id = add_call[0][0]
    batch = add_call[0][1]

    assert called_playlist_id == platform_playlist_id
    assert set(batch) == {"111", "222"}


@pytest.mark.asyncio
async def test_push_to_platform_handles_bare_ids(db: AsyncSession) -> None:
    """_push_to_platform passes bare IDs to provider as-is."""
    provider_mock = _make_provider_mock()
    svc = _make_sync_service(db, provider_mock)

    on_local_only = {"333"}
    added = await svc._push_to_platform(
        platform_playlist_id="12345678:42",
        on_local_only=on_local_only,
    )

    assert added == 1

    add_call = provider_mock.add_tracks_to_playlist.call_args
    batch = add_call[0][1]
    assert "333" in batch
