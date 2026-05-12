"""Regression: ``entity_update(set, …)`` must enforce the BPM-range
invariant across the merged (old, partial) values.

``SetUpdate._validate_bpm_range`` only catches the case where BOTH
``target_bpm_min`` and ``target_bpm_max`` come in the same payload —
it has no view of the existing row. Partial updates that touch only
one side used to slip through, leaving the row with ``min > max``
(violating the same invariant ``SetCreate`` enforces). The
dispatcher now reads the existing row and validates the merged pair.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_partial_update_bpm_min_exceeds_existing_max_rejected(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    """Existing row has ``max=140``. Caller bumps ``min`` to 150 alone —
    must be rejected with a clear message naming the merged values."""
    existing = MagicMock(target_bpm_min=120, target_bpm_max=140)
    mock_uow.sets.get = AsyncMock(return_value=existing)
    with pytest.raises(Exception, match=r"target_bpm_min \(150\).*target_bpm_max \(140\)"):
        await mcp_client.call_tool(
            "entity_update",
            {"entity": "set", "id": 1, "data": {"target_bpm_min": 150}},
        )


@pytest.mark.asyncio
async def test_partial_update_bpm_max_below_existing_min_rejected(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    """Mirror: existing min=120, caller drops max to 100 alone."""
    existing = MagicMock(target_bpm_min=120, target_bpm_max=140)
    mock_uow.sets.get = AsyncMock(return_value=existing)
    with pytest.raises(Exception, match=r"target_bpm_min \(120\).*target_bpm_max \(100\)"):
        await mcp_client.call_tool(
            "entity_update",
            {"entity": "set", "id": 1, "data": {"target_bpm_max": 100}},
        )


@pytest.mark.asyncio
async def test_partial_update_only_one_side_within_range_passes(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    """Sanity: ``min=125`` with existing ``max=140`` stays valid — the
    new invariant gate must NOT reject valid partial updates."""
    existing = MagicMock(target_bpm_min=120, target_bpm_max=140)
    mock_uow.sets.get = AsyncMock(return_value=existing)
    mock_uow.sets.update = AsyncMock(return_value=existing)
    # If the gate falsely fires, this raises Exception matching our msg.
    # Other validation failures downstream are out of scope.
    try:
        await mcp_client.call_tool(
            "entity_update",
            {"entity": "set", "id": 1, "data": {"target_bpm_min": 125}},
        )
    except Exception as exc:
        assert "target_bpm_min" not in str(exc) or "after applying partial update" not in str(exc)
