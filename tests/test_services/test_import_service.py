"""Tests for ImportService — return values and playlist linking.

Regression for ОШИБКА #2 and #3 in
``docs/reports/mcp-tools-test-2026-04-07.md``:

* #3 — ``import_tracks`` did not return the local IDs of newly created or
  pre-existing tracks. Callers had no way to look them up after the call.
* #2 (partial) — supporting playlist linking from ``import_tracks`` so the
  MCP tool's ``playlist_id`` parameter can stop being a no-op.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import Provider
from app.db.models.playlist import Playlist
from app.db.models.track import Track
from app.db.repositories.playlist import PlaylistRepository
from app.db.repositories.track import TrackRepository
from app.services.import_service import ImportService


def _make_service(db: AsyncSession) -> ImportService:
    track_repo = TrackRepository(db)
    provider_mock = AsyncMock()
    provider_mock.provider = Provider.YANDEX_MUSIC
    provider_mock.get_tracks = AsyncMock(return_value=[])
    return ImportService(track_repo=track_repo, provider=provider_mock)


@pytest.mark.asyncio
async def test_import_returns_id_mapping_for_new_tracks(db: AsyncSession) -> None:
    """Newly created tracks must be returned in id_mapping (external_id → local_id)."""
    svc = _make_service(db)

    result = await svc.import_tracks(track_refs=["111", "222"])

    assert result["imported"] == 2
    assert result["skipped"] == 0
    assert "id_mapping" in result, "ОШИБКА #3: id_mapping missing from result"
    mapping = result["id_mapping"]
    assert set(mapping.keys()) == {"111", "222"}
    assert all(isinstance(v, int) for v in mapping.values())
    assert mapping["111"] != mapping["222"]


@pytest.mark.asyncio
async def test_import_returns_id_mapping_for_existing_tracks(db: AsyncSession) -> None:
    """Re-import of existing tracks must still return their local IDs."""
    db.add(Track(title="seed-track", status=0))
    await db.flush()

    svc = _make_service(db)

    first = await svc.import_tracks(track_refs=["333"])
    assert first["imported"] == 1
    new_local_id = first["id_mapping"]["333"]
    assert new_local_id != 1, "test setup must decouple track.id from external_id.id"

    second = await svc.import_tracks(track_refs=["333"])
    assert second["imported"] == 0
    assert second["skipped"] == 1
    assert second["id_mapping"]["333"] == new_local_id, (
        "ОШИБКА #3: existing tracks must also appear in id_mapping"
    )


@pytest.mark.asyncio
async def test_import_with_playlist_id_adds_tracks_to_playlist(
    db: AsyncSession,
) -> None:
    """``playlist_id`` parameter must actually add imported tracks to the playlist."""
    playlist_repo = PlaylistRepository(db)
    playlist = Playlist(name="test-import-playlist", source_of_truth="local")
    db.add(playlist)
    await db.flush()

    svc = _make_service(db)
    result = await svc.import_tracks(
        track_refs=["444", "555"],
        playlist_id=playlist.id,
    )

    assert result["imported"] == 2
    assert result.get("playlist_added") == 2, (
        "ОШИБКА #2: playlist_id was a no-op, must actually add tracks"
    )

    track_ids_in_playlist = set(await playlist_repo.get_track_ids(playlist.id))
    expected = set(result["id_mapping"].values())
    assert track_ids_in_playlist == expected
