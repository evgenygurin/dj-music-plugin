"""Tests for PlaylistService — platform_ids JSON serialization (B2)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.playlist import PlaylistRepository
from app.services.playlist_service import PlaylistService


def _make_playlist_service(db: AsyncSession) -> PlaylistService:
    return PlaylistService(repo=PlaylistRepository(db))


# ── B2: manage_playlist serializes platform_ids dict → JSON ──


@pytest.mark.asyncio
async def test_update_platform_ids_dict_serialized_to_json(db: AsyncSession) -> None:
    """update() should serialize dict platform_ids to JSON string for Text column."""
    svc = _make_playlist_service(db)

    playlist = await svc.create("Test Playlist")
    assert playlist.platform_ids is None

    updated = await svc.update(
        playlist.id,
        platform_ids={"yandex_music": "1234"},
    )

    # platform_ids column is Text — must be a JSON string, not a dict
    assert isinstance(updated.platform_ids, str)
    parsed = json.loads(updated.platform_ids)
    assert parsed == {"yandex_music": "1234"}


@pytest.mark.asyncio
async def test_update_platform_ids_list_serialized_to_json(db: AsyncSession) -> None:
    """update() should also serialize list values to JSON string."""
    svc = _make_playlist_service(db)

    playlist = await svc.create("Test PL 2")

    updated = await svc.update(
        playlist.id,
        platform_ids=["ym:1234", "spotify:5678"],
    )

    assert isinstance(updated.platform_ids, str)
    parsed = json.loads(updated.platform_ids)
    assert parsed == ["ym:1234", "spotify:5678"]


@pytest.mark.asyncio
async def test_update_string_field_not_double_serialized(db: AsyncSession) -> None:
    """update() should not double-serialize plain string values."""
    svc = _make_playlist_service(db)

    playlist = await svc.create("Old Name")

    updated = await svc.update(playlist.id, name="New Name")
    assert updated.name == "New Name"
    # name should remain a plain string, not JSON-encoded
    assert not updated.name.startswith('"')


@pytest.mark.asyncio
async def test_update_platform_ids_already_string_stays_string(db: AsyncSession) -> None:
    """update() with a pre-serialized JSON string should store it as-is."""
    svc = _make_playlist_service(db)

    playlist = await svc.create("PL String")

    pre_serialized = '{"ym": "999"}'
    updated = await svc.update(playlist.id, platform_ids=pre_serialized)

    # String stays as string (not double-encoded)
    assert updated.platform_ids == pre_serialized
    parsed = json.loads(updated.platform_ids)
    assert parsed == {"ym": "999"}
