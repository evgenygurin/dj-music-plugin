"""transition_window — find optimal mix-in/out window between two tracks."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from app.domain.performance.cue_points import find_transition_window
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.transition_window import TransitionWindowResult
from app.server.di import get_uow


async def _get_sections(uow: UnitOfWork, track_id: int) -> list[dict[str, Any]]:
    sections = await uow.track_sections.list_by_track(track_id)
    return [
        {
            "track_id": s.track_id,
            "section_type": s.section_type,
            "start_ms": s.start_ms,
            "end_ms": s.end_ms,
            "energy": s.energy,
            "confidence": s.confidence,
        }
        for s in sections
    ]


@tool(
    name="transition_window",
    tags={"namespace:performance"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Find the optimal transition window between two tracks. "
        "Uses track section structure to determine when to mix out of "
        "track A (using its outro) and mix in track B (using its intro)."
    ),
    meta={"timeout_s": 5.0},
    timeout=5.0,
)
async def transition_window(
    from_track_id: Annotated[int, Field(ge=1, description="Outgoing track ID")],
    to_track_id: Annotated[int, Field(ge=1, description="Incoming track ID")],
    bpm: Annotated[float | None, Field(ge=20, le=300, description="Override BPM")] = None,
    preferred_bars: Annotated[
        int, Field(ge=4, le=128, description="Preferred transition length in bars")
    ] = 32,
    uow: UnitOfWork = Depends(get_uow),
) -> TransitionWindowResult:
    from_sections = await _get_sections(uow, from_track_id)
    to_sections = await _get_sections(uow, to_track_id)

    if bpm is None:
        features = await uow.track_features.get_by_track_id(from_track_id)
        bpm = float(getattr(features, "bpm", 128) or 128)

    win = find_transition_window(from_sections, to_sections, bpm, preferred_bars=preferred_bars)

    return TransitionWindowResult(
        from_track_id=win.from_track_id,
        to_track_id=win.to_track_id,
        mix_out_start_ms=win.mix_out_start_ms,
        mix_out_end_ms=win.mix_out_end_ms,
        mix_in_start_ms=win.mix_in_start_ms,
        mix_in_end_ms=win.mix_in_end_ms,
        recommendation=win.recommendation,
    )
