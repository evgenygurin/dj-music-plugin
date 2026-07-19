"""MCP tool: energy_budget."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.tools import tool

from app.domain.multi_deck.energy_budget import compute_energy_budget
from app.domain.multi_deck.models import StemLayer
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow


@tool(name="energy_budget", annotations={"readOnlyHint": True, "idempotentHint": True})
async def energy_budget(
    layers: list[dict[str, str | int]],
    gain_db: list[float] | None = None,
    target_lufs: float = -8.0,
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any]:
    """Compute combined energy budget across active decks.

    Args:
        layers: List of {track_id: int, stem_name: str}.
        gain_db: Per-layer gain adjustment in dB (same order as layers).
        target_lufs: Target integrated LUFS (default -8.0).
    """
    stem_layers = [
        StemLayer(track_id=int(lyr["track_id"]), stem_name=str(lyr["stem_name"])) for lyr in layers
    ]
    result = await compute_energy_budget(uow, stem_layers, gain_db, target_lufs)
    return {
        "total_lufs": result.total_lufs,
        "headroom_db": result.headroom_db,
        "per_band": {
            band: {
                "total_lufs": bb.total_lufs,
                "headroom_db": bb.headroom_db,
                "warning": bb.warning,
            }
            for band, bb in result.per_band.items()
        },
        "recommendation": result.recommendation,
    }
