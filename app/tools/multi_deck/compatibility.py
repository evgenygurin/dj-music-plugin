"""MCP tool: stem_vertical_compatibility."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.tools import tool

from app.domain.multi_deck.compatibility import compute_stem_compatibility
from app.domain.multi_deck.models import StemLayer
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow


@tool(name="stem_vertical_compatibility", annotations={"readOnlyHint": True, "idempotentHint": True})
async def stem_vertical_compatibility(
    layers: list[dict[str, str | int]],
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any]:
    """Check N-way stem frequency/key/BPM compatibility for simultaneous playback.

    Args:
        layers: List of {track_id: int, stem_name: str} — stems to check.
    """
    stem_layers = [StemLayer(track_id=int(lyr["track_id"]), stem_name=str(lyr["stem_name"])) for lyr in layers]
    result = await compute_stem_compatibility(uow, stem_layers)
    return {
        "overall_score": result.overall_score,
        "hard_reject": result.hard_reject,
        "per_band": {band: {"score": bs.score, "clash": bs.clash, "culprits": bs.culprits} for band, bs in result.per_band.items()},
        "key_compatibility": result.key_compatibility,
        "bpm_compatibility": result.bpm_compatibility,
        "recommendations": result.recommendations,
    }
