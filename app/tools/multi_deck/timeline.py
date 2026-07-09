"""MCP tools: timeline_overlay, find_loops."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.tools import tool

from app.domain.multi_deck.loop_finder import find_loops as _find_loops
from app.domain.multi_deck.timeline import build_timeline_overlay
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow


@tool(name="timeline_overlay", annotations={"readOnlyHint": True, "idempotentHint": True})
async def timeline_overlay(
    track_ids: list[int],
    align_mode: str = "downbeat",
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any]:
    """Show sections of multiple tracks on a unified timeline aligned by downbeat.

    Args:
        track_ids: Track IDs to overlay.
        align_mode: Alignment mode (only "downbeat" currently).
    """
    return await build_timeline_overlay(uow, track_ids, align_mode)


@tool(name="find_loops", annotations={"readOnlyHint": True, "idempotentHint": True})
async def find_loops(
    track_id: int,
    min_bars: int = 8,
    max_bars: int = 32,
    exclude_vocals: bool = True,
    min_energy_stability: float = 0.7,
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any]:
    """Find loopable sections in a track for sustained multi-deck layering.

    Args:
        track_id: Track to scan.
        min_bars/max_bars: Loop length range.
        exclude_vocals: Skip sections with vocal energy > 0.15.
        min_energy_stability: Minimum energy stability (0-1).
    """
    return await _find_loops(uow, track_id, min_bars, max_bars, exclude_vocals, min_energy_stability)
