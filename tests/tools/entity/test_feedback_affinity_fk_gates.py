"""Regression: ``entity_create(track_feedback|track_affinity)`` must reject
references to non-existent tracks.

Both entities carry FKs to ``tracks.id``. SQLite (default FK enforcement
off, our test default) silently kept orphan rows; PostgreSQL would
reject them with an opaque ``ForeignKeyViolationError`` at INSERT. The
dispatcher gate now validates the references up front and raises a
typed ``ValidationError`` naming the bad id(s).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_track_feedback_rejects_ghost_track_id(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    mock_uow.tracks.get = AsyncMock(return_value=None)
    with pytest.raises(Exception, match=r"track_id .* does not reference"):
        await mcp_client.call_tool(
            "entity_create",
            {"entity": "track_feedback", "data": {"track_id": 99999, "rating": 3}},
        )
    mock_uow.tracks.get.assert_awaited_once_with(99999)


@pytest.mark.asyncio
async def test_track_affinity_rejects_ghost_track_a_id(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    mock_uow.tracks.get = AsyncMock(return_value=None)
    with pytest.raises(Exception, match=r"missing track.*track_a_id=99999"):
        await mcp_client.call_tool(
            "entity_create",
            {
                "entity": "track_affinity",
                "data": {"track_a_id": 99999, "track_b_id": 2, "avg_score": 0.5},
            },
        )


@pytest.mark.asyncio
async def test_track_affinity_lists_all_missing_sides(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    """When BOTH sides are missing, the message names both — so the
    caller doesn't have to re-submit twice to discover the second bad id.
    """
    mock_uow.tracks.get = AsyncMock(return_value=None)
    with pytest.raises(Exception) as info:
        await mcp_client.call_tool(
            "entity_create",
            {
                "entity": "track_affinity",
                "data": {"track_a_id": 99999, "track_b_id": 98765, "avg_score": 0.5},
            },
        )
    msg = str(info.value)
    assert "track_a_id=99999" in msg
    assert "track_b_id=98765" in msg
