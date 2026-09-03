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
    """Show sections of multiple tracks on a unified timeline aligned by downbeat."""

    class Reader:
        def __init__(self, repo: UnitOfWork) -> None:
            self._repo = repo

        async def get_track_sections(self, track_id: int) -> list[dict[str, Any]]:
            return await self._repo.track_features.get_track_sections(track_id)

        async def get_beatgrids(self, track_id: int) -> list[Any]:
            return await self._repo.audio_files.get_beatgrids(track_id)

        async def get_by_track_id(self, track_id: int) -> Any:
            return await self._repo.track_features.get_by_track_id(track_id)

    return await build_timeline_overlay(Reader(uow), track_ids, align_mode)


@tool(name="find_loops", annotations={"readOnlyHint": True, "idempotentHint": True})
async def find_loops(
    track_id: int,
    min_bars: int = 8,
    max_bars: int = 32,
    exclude_vocals: bool = True,
    min_energy_stability: float = 0.7,
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any]:
    """Find loopable sections in a track for sustained multi-deck layering."""
    sections = await uow.track_features.get_track_sections(track_id)
    features_row = await uow.track_features.get_by_track_id(track_id)
    bpm = features_row.bpm if features_row and features_row.bpm is not None else None
    return _find_loops(
        sections, bpm, track_id, min_bars, max_bars, exclude_vocals, min_energy_stability
    )
