"""Regression: ``entity_create(transition_history, …)`` must reject ghost
``from_track_id`` / ``to_track_id``.

Two FK references — same shape as ``track_affinity`` (committed in
round-6). Round-10 manual testing confirmed the gap.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_ghost_both_sides_lists_each_missing_id(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    mock_uow.tracks.get = AsyncMock(return_value=None)
    with pytest.raises(Exception) as info:
        await mcp_client.call_tool(
            "entity_create",
            {
                "entity": "transition_history",
                "data": {"from_track_id": 99999, "to_track_id": 99998},
            },
        )
    msg = str(info.value)
    assert "from_track_id=99999" in msg
    assert "to_track_id=99998" in msg


@pytest.mark.asyncio
async def test_ghost_one_side_only(mcp_client: Client, mock_uow: MagicMock) -> None:
    """Existing ``to_track_id``, missing ``from_track_id`` — message names
    only the missing side."""

    # tracks.get(99999) -> None (missing); tracks.get(2) -> exists.
    async def _maybe(tid: int) -> MagicMock | None:
        return None if tid == 99999 else MagicMock(id=tid)

    mock_uow.tracks.get = AsyncMock(side_effect=_maybe)
    with pytest.raises(Exception) as info:
        await mcp_client.call_tool(
            "entity_create",
            {
                "entity": "transition_history",
                "data": {"from_track_id": 99999, "to_track_id": 2},
            },
        )
    msg = str(info.value)
    assert "from_track_id=99999" in msg
    assert "to_track_id=" not in msg, "should not name the side that exists"
