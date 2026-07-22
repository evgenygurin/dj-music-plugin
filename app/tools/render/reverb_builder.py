"""reverb_builder — construct reverb effects for DJ sets."""

from __future__ import annotations

from typing import Annotated

from fastmcp.tools import tool
from pydantic import Field

from app.audio.effects.reverb import REVERB_PRESETS, ReverbIR, ReverbSpace
from app.schemas.reverb import ReverbResult
from app.shared.errors import ValidationError


@tool(
    name="reverb_builder",
    tags={"namespace:render:effects"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Build a reverb effect for DJ sets. Presets: techno_hall (RT60=2.5s), "
        "techno_cathedral (5s), industrial_warehouse (3s, bright), "
        "dub_plate (1.8s, warm), minimal_room (1s, tight)."
    ),
    meta={"timeout_s": 10.0},
    timeout=10.0,
)
async def reverb_builder(
    preset: Annotated[
        str | None,
        Field(description="Preset: techno_hall, techno_cathedral, etc."),
    ] = None,
    decay_s: Annotated[
        float | None, Field(ge=0.1, le=10.0, description="RT60 decay time (seconds)")
    ] = None,
    pre_delay_ms: Annotated[
        float | None, Field(ge=0, le=200, description="Pre-delay (milliseconds)")
    ] = None,
    mix_ratio: Annotated[
        float | None, Field(ge=0.0, le=1.0, description="Wet/dry mix ratio")
    ] = None,
    space: Annotated[
        str | None,
        Field(description="room, hall, cathedral, warehouse, plate, spring"),
    ] = None,
) -> ReverbResult:
    if preset is not None:
        if preset not in REVERB_PRESETS:
            raise ValidationError(
                f"unknown preset {preset!r}; valid: {sorted(REVERB_PRESETS.keys())}",
                details={"preset": preset},
            )
        rv = REVERB_PRESETS[preset]
    else:
        rv = ReverbIR(
            decay_s=decay_s or 2.5,
            pre_delay_ms=pre_delay_ms or 20.0,
            mix_ratio=mix_ratio or 0.35,
            space=ReverbSpace(space or "hall"),
        )
    return ReverbResult(
        preset_name=preset,
        decay_s=rv.decay_s,
        pre_delay_ms=rv.pre_delay_ms,
        mix_ratio=rv.mix_ratio,
        space=rv.space.value,
        sample_rate=rv.sample_rate,
        total_samples=rv.total_samples,
        highpass_hz=rv.highpass_hz,
        lowpass_hz=rv.lowpass_hz,
    )
