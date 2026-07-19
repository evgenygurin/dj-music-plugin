"""MCP tool: bpm_ratio_analyzer."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.tools import tool

from app.domain.multi_deck.bpm_ratio import analyze_bpm_ratio
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow


@tool(name="bpm_ratio_analyzer", annotations={"readOnlyHint": True, "idempotentHint": True})
async def bpm_ratio_analyzer(
    bpm_a: float,
    bpm_min: float = 40,
    bpm_max: float = 200,
    ratios: list[str] | None = None,
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any]:
    """Find musically useful BPM ratios (3:4, 2:3, etc.) for dual-BPM storytelling.

    Args:
        bpm_a: Source BPM.
        bpm_min/max: BPM search range.
        ratios: List of ratio labels (e.g. ["3:4", "2:3"]). Default: all.
    """
    result = await analyze_bpm_ratio(uow, bpm_a, (bpm_min, bpm_max), ratios)
    return {
        "bpm_a": result.bpm_a,
        "matches": [
            {
                "bpm_b": m.bpm_b,
                "ratio": m.ratio,
                "ratio_label": m.ratio_label,
                "error_pct": m.error_pct,
                "bars_to_align": m.bars_to_align,
                "seconds_to_align": m.seconds_to_align,
            }
            for m in result.matches
        ],
    }
