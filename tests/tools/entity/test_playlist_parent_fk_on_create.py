"""Regression: ``entity_create(playlist, data={parent_id: …})`` must
reject references to a non-existent parent playlist.

``DjPlaylist.parent_id`` is a real FK to ``dj_playlists.id``. SQLite
(default FK enforcement off, our test default) silently kept orphan
rows; PostgreSQL would have rejected with an opaque
``ForeignKeyViolationError``. Mirror pattern of the other create-path
FK gates (``set.source_playlist_id``, ``track_feedback.track_id``,
``track_affinity.track_{a,b}_id``).
"""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_create_playlist_rejects_ghost_parent_id(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    mock_uow.playlists.get = AsyncMock(return_value=None)
    with pytest.raises(Exception, match=r"parent_id 99999 does not reference"):
        await mcp_client.call_tool(
            "entity_create",
            {"entity": "playlist", "data": {"name": "Orphan", "parent_id": 99999}},
        )
    mock_uow.playlists.get.assert_awaited_once_with(99999)


@pytest.mark.asyncio
async def test_create_playlist_without_parent_skips_gate(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    """parent_id=None (the default) must NOT trigger the gate — root
    playlists are valid."""
    mock_uow.playlists.get = AsyncMock(return_value=None)
    mock_uow.playlists.create = AsyncMock(return_value=MagicMock(id=1))
    # Other validators may complain — out of scope for this regression.
    # What matters: ``playlists.get`` must NOT be called when no
    # parent_id is supplied.
    with contextlib.suppress(Exception):
        await mcp_client.call_tool(
            "entity_create",
            {"entity": "playlist", "data": {"name": "Root"}},
        )
    mock_uow.playlists.get.assert_not_awaited()
