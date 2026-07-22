"""cue_points — auto-detect 8 hot cues (A-H) from track structure."""

from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from app.domain.performance.cue_points import CueType, detect_cues
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.cue_points import CueItem, CuePointsResult
from app.server.di import get_uow

CUE_LABELS = {
    CueType.GRID: "A: Grid",
    CueType.BUILD: "B: Build",
    CueType.DROP: "C: Drop",
    CueType.BREAKDOWN: "D: Break",
    CueType.OUTRO: "F: Outro",
    CueType.PRE_DROP: "G: Pre-drop",
    CueType.LOOP_IN: "H: Loop",
}


@tool(
    name="cue_points",
    tags={"namespace:performance"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Auto-detect 8 hot cues (A-H) for a track from its detected structure. "
        "Uses the StructureAnalyzer output (sections: intro, build, drop, "
        "breakdown, outro). Returns positions, types, and labels suitable for "
        "Rekordbox XML export."
    ),
    meta={"timeout_s": 5.0},
    timeout=5.0,
)
async def cue_points(
    track_id: Annotated[int, Field(ge=1, description="Track ID")],
    uow: UnitOfWork = Depends(get_uow),
) -> CuePointsResult:
    sections = await uow.track_sections.list_by_track(track_id)
    features = await uow.track_features.get_by_track_id(track_id)
    track = await uow.tracks.get(track_id)

    bpm = float(getattr(features, "bpm", 0) or 0)
    fd_ms = float(getattr(features, "first_downbeat_ms", 0) or 0)
    dur_ms = int(getattr(track, "duration_ms", 0) or 0)

    section_dicts = [
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

    cue_set = detect_cues(section_dicts, bpm, fd_ms, dur_ms)

    return CuePointsResult(
        track_id=track_id,
        bpm=bpm,
        cues=[
            CueItem(
                index=c.index,
                cue_type=c.cue_type.name,
                position_ms=c.position_ms,
                label=c.label,
                color=c.color,
            )
            for c in cue_set.cues
        ],
    )
