"""energy_arc_plan — generate target energy/BPM slots for a DJ set."""
from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.tools import tool
from pydantic import Field

from app.domain.performance.energy_arc import ARC_PRESETS
from app.schemas.energy_arc import ArcSlotResult, EnergyArcResult

VALID_SHAPES = Literal["roller", "journey", "warehouse", "festival"]


@tool(
    name="energy_arc_plan",
    tags={"namespace:render:config"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Generate an energy arc plan for a DJ set. Returns target BPM and energy "
        "for each track position. Use these slots to filter candidate tracks by "
        "BPM/energy range via entity_list(track_features). "
        "Shapes: roller (steady climb), journey (two peaks, Nina-style), "
        "warehouse (deep/sustained), festival (quick ramp, intense)."
    ),
    meta={"timeout_s": 5.0},
    timeout=5.0,
)
async def energy_arc_plan(
    shape: Annotated[
        str,
        Field(description="Arc shape: roller, journey, warehouse, festival"),
    ] = "roller",
    num_tracks: Annotated[
        int, Field(ge=3, le=30, description="Number of tracks in the set")
    ] = 16,
    bpm_start: Annotated[
        float, Field(ge=100, le=160, description="Starting BPM")
    ] = 126.0,
    bpm_peak: Annotated[
        float, Field(ge=100, le=160, description="Peak BPM")
    ] = 136.0,
    bpm_end: Annotated[
        float, Field(ge=100, le=160, description="Ending BPM")
    ] = 128.0,
) -> EnergyArcResult:
    factory = ARC_PRESETS.get(shape)
    if factory is None:
        raise ValueError(f"unknown shape {shape!r}; valid: {sorted(ARC_PRESETS.keys())}")
    arc = factory(num_tracks)
    arc.target_bpm_start = bpm_start
    arc.target_bpm_peak = bpm_peak
    arc.target_bpm_end = bpm_end
    slots = arc.build_slots()
    return EnergyArcResult(
        shape=shape,
        num_tracks=num_tracks,
        bpm_start=bpm_start,
        bpm_peak=bpm_peak,
        bpm_end=bpm_end,
        slots=[
            ArcSlotResult(
                position=s.position,
                target_bpm=s.target_bpm,
                target_energy=s.target_energy,
                label=s.label,
            )
            for s in slots
        ],
    )
