"""Regression: ``entity_update(transition, data={fx_type: ...})`` must
reject any value that is not one of the seven ``NeuralMixTransition``
enum members.

``TransitionUpdate.fx_type`` is declared as ``str | None`` on the
schema (the schema cannot import ``app.domain``), so the only string
constraints were ``min_length=1, max_length=50`` — a typo like
``"lol_wut"`` used to land in the row and either crash the Neural Mix
recipe builder downstream or silently fall back to defaults. The
dispatcher now mirrors the ``template_name`` check pattern and
validates against the actual enum.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_unknown_fx_type_rejected(mcp_client: Client, mock_uow: MagicMock) -> None:
    mock_uow.transitions.get = AsyncMock(return_value=MagicMock(id=1))
    with pytest.raises(Exception, match=r"unknown fx_type 'lol_wut'"):
        await mcp_client.call_tool(
            "entity_update",
            {"entity": "transition", "id": 1, "data": {"fx_type": "lol_wut"}},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value",
    [
        "fade",
        "echo_out",
        "vocal_sustain",
        "harmonic_sustain",
        "drum_swap",
        "vocal_cut",
        "drum_cut",
    ],
)
async def test_all_seven_neural_mix_values_pass(
    mcp_client: Client, mock_uow: MagicMock, value: str
) -> None:
    """Sanity: every documented Neural Mix transition still gets through
    the new gate. Reaching the downstream repo call means validation
    cleared (NotFoundError below is fine, we're only asserting the
    fx_type gate didn't fire)."""
    mock_uow.transitions.get = AsyncMock(return_value=None)
    with pytest.raises(Exception) as info:
        await mcp_client.call_tool(
            "entity_update",
            {"entity": "transition", "id": 1, "data": {"fx_type": value}},
        )
    assert "unknown fx_type" not in str(info.value)
