"""Audit O-1: ``local://tracks/{id}.primary_artist_name`` must populate
when ``track_artists`` rows exist for the track.

Resource layer test (mocks UoW): the resource must call
``uow.tracks.get_primary_artist_name`` and inject the result into the
serialised payload, so the field is no longer always ``null``.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.resources.track import track_view


@pytest.mark.asyncio
async def test_track_view_includes_primary_artist_name() -> None:
    track = MagicMock(
        id=42,
        title="Heaven",
        sort_title="heaven",
        duration_ms=258510,
        status=0,
        primary_artist_name=None,
    )
    uow = MagicMock()
    uow.tracks = MagicMock()
    uow.tracks.get = AsyncMock(return_value=track)
    uow.tracks.get_primary_artist_name = AsyncMock(return_value="Amelie Lens")

    payload = json.loads(await track_view(id=42, uow=uow))
    assert payload["primary_artist_name"] == "Amelie Lens"
    uow.tracks.get_primary_artist_name.assert_awaited_once_with(42)


@pytest.mark.asyncio
async def test_track_view_primary_artist_none_for_track_without_artists() -> None:
    track = MagicMock(
        id=43,
        title="X",
        sort_title="x",
        duration_ms=200000,
        status=0,
        primary_artist_name=None,
    )
    uow = MagicMock()
    uow.tracks = MagicMock()
    uow.tracks.get = AsyncMock(return_value=track)
    uow.tracks.get_primary_artist_name = AsyncMock(return_value=None)

    payload = json.loads(await track_view(id=43, uow=uow))
    assert payload["primary_artist_name"] is None
