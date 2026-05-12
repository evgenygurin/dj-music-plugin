"""Regression: ``entity_create/update(set, source_playlist_id=…)`` must
verify the playlist exists.

``DjSet.source_playlist_id`` is a real FK to ``dj_playlists.id``.
SQLite (default FK enforcement off, our test default) would silently
accept a bogus id and write an orphan row; PostgreSQL would reject it
with an opaque ``ForeignKeyViolationError`` long after the dispatcher
could have produced a clean message. The create/update gates now
verify the playlist exists and raise a typed
``ValidationError("source_playlist_id N does not reference an
existing playlist")``.
"""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_create_set_rejects_ghost_source_playlist_id(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    mock_uow.playlists.get = AsyncMock(return_value=None)
    with pytest.raises(Exception, match=r"source_playlist_id .* does not reference"):
        await mcp_client.call_tool(
            "entity_create",
            {"entity": "set", "data": {"name": "Bad", "source_playlist_id": 99999}},
        )
    mock_uow.playlists.get.assert_awaited_once_with(99999)


@pytest.mark.asyncio
async def test_update_set_rejects_ghost_source_playlist_id(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    mock_uow.playlists.get = AsyncMock(return_value=None)
    with pytest.raises(Exception, match=r"source_playlist_id .* does not reference"):
        await mcp_client.call_tool(
            "entity_update",
            {"entity": "set", "id": 1, "data": {"source_playlist_id": 99999}},
        )


@pytest.mark.asyncio
async def test_update_set_allows_explicit_null(mcp_client: Client, mock_uow: MagicMock) -> None:
    """``source_playlist_id=None`` (explicit unlink) must NOT trigger the
    FK gate — there's no id to verify."""
    mock_uow.sets.get = AsyncMock(return_value=MagicMock(id=1))
    mock_uow.sets.update = AsyncMock(return_value=MagicMock(id=1))
    # If the FK gate fires for None, it'll call playlists.get; assert it
    # never does.
    mock_uow.playlists.get = AsyncMock(return_value=None)
    # Other validators may complain — that's outside this regression's
    # scope. The only thing that matters: playlists.get must NOT be
    # called for ``source_playlist_id=None`` (no FK gate trigger).
    with contextlib.suppress(Exception):
        await mcp_client.call_tool(
            "entity_update",
            {"entity": "set", "id": 1, "data": {"source_playlist_id": None}},
        )
    mock_uow.playlists.get.assert_not_awaited()
