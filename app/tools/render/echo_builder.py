"""echo_builder — construct delay/echo effects for DJ transitions."""
from __future__ import annotations

from typing import Annotated

from fastmcp.tools import tool
from pydantic import Field

from app.audio.effects.echo_delay import ECHO_PRESETS
from app.schemas.echo_delay import EchoResult
from app.shared.errors import ValidationError


@tool(
    name="echo_builder",
    tags={"namespace:render:effects"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Build a delay/echo effect for DJ transitions. Presets: techno_standard "
        "(375ms dotted-8th), vocal_throw (500ms quarter with pre-delay), "
        "industrial_stutter (94ms 16th-note stutter), dub_space (750ms half-note), "
        "acid_bounce (188ms triplet). Custom parameters available when preset=None."
    ),
    meta={"timeout_s": 5.0},
    timeout=5.0,
)
async def echo_builder(
    preset: Annotated[
        str | None,
        Field(description="Preset name: techno_standard, vocal_throw, etc."),
    ] = None,
    delay_ms: Annotated[
        float | None, Field(ge=1, le=2000, description="Delay time in milliseconds")
    ] = None,
    decay: Annotated[
        float | None, Field(ge=0.0, le=1.0, description="Feedback decay")
    ] = None,
    taps: Annotated[
        int | None, Field(ge=1, le=10, description="Number of echo taps")
    ] = None,
    wet_dry: Annotated[
        float | None, Field(ge=0.0, le=1.0, description="Wet/dry ratio")
    ] = None,
    stereo_spread: Annotated[
        float | None, Field(ge=0.0, le=1.0, description="Stereo spread")
    ] = None,
) -> EchoResult:
    if preset is not None:
        if preset not in ECHO_PRESETS:
            raise ValidationError(
                f"unknown preset {preset!r}; valid: {sorted(ECHO_PRESETS.keys())}",
                details={"preset": preset},
            )
        ep = ECHO_PRESETS[preset]
    else:
        from app.audio.effects.echo_delay import EchoPlan

        ep = EchoPlan(
            delay_ms=delay_ms or 375.0,
            decay=decay or 0.4,
            taps=taps or 3,
            wet_dry_ratio=wet_dry or 0.5,
            stereo_spread=stereo_spread or 0.4,
        )
    return EchoResult(
        preset_name=preset,
        delay_ms=ep.effective_delay_ms,
        decay=ep.decay,
        taps=ep.taps,
        wet_dry_ratio=ep.wet_dry_ratio,
        stereo_spread=ep.stereo_spread,
        ffmpeg_aecho_expr=ep.ffmpeg_aecho_expr(),
    )
