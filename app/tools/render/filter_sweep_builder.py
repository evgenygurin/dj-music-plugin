"""filter_sweep_builder — construct filter sweep effects for DJ transitions."""
from __future__ import annotations

from typing import Annotated

from fastmcp.tools import tool
from pydantic import Field

from app.audio.effects.filter_sweep import (
    FILTER_PRESETS,
    FilterSweepPlan,
    SweepCurve,
    SweepDirection,
)
from app.schemas.filter_sweep import FilterSweepResult, FilterSweepSide
from app.shared.errors import ValidationError


@tool(
    name="filter_sweep_builder",
    tags={"namespace:render:effects"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Build a filter sweep for DJ transitions. Pick a preset or define custom "
        "parameters. Returns ffmpeg-ready expressions. Presets: classic_lowpass "
        "(smooth 14k→200Hz), acid_squelch (resonant 8k→400Hz), industrial_cut "
        "(brutal 20k→80Hz), hypnotic_wash (gentle 12k→300Hz), dub_echo_sweep "
        "(warm 10k→500Hz)."
    ),
    meta={"timeout_s": 5.0},
    timeout=5.0,
)
async def filter_sweep_builder(
    preset: Annotated[
        str | None,
        Field(description="Preset name: classic_lowpass, acid_squelch, etc."),
    ] = None,
    start_freq_hz: Annotated[
        float | None,
        Field(ge=20, le=20000, description="Sweep start frequency (Hz)"),
    ] = None,
    end_freq_hz: Annotated[
        float | None,
        Field(ge=20, le=20000, description="Sweep end frequency (Hz)"),
    ] = None,
    direction: Annotated[
        str | None,
        Field(description="close (lowpass down), open (highpass up), peak (bandpass)"),
    ] = None,
    curve: Annotated[
        str | None,
        Field(description="linear, exponential, logarithmic"),
    ] = None,
    resonance: Annotated[
        float | None,
        Field(ge=0.1, le=5.0, description="Filter resonance (Q factor)"),
    ] = None,
) -> FilterSweepResult:
    if preset is not None:
        if preset not in FILTER_PRESETS:
            raise ValidationError(
                f"unknown preset {preset!r}; valid: {sorted(FILTER_PRESETS.keys())}",
                details={"preset": preset},
            )
        tp = FILTER_PRESETS[preset]
        result = FilterSweepResult(preset_name=preset)
        if tp.outgoing:
            result.outgoing = FilterSweepSide(
                start_freq_hz=tp.outgoing.start_freq_hz,
                end_freq_hz=tp.outgoing.end_freq_hz,
                direction=tp.outgoing.direction.value,
                curve=tp.outgoing.curve.value,
                resonance=tp.outgoing.resonance,
                ffmpeg_expr=tp.outgoing.ffmpeg_lowpass_expr(8.0),
            )
        if tp.incoming:
            result.incoming = FilterSweepSide(
                start_freq_hz=tp.incoming.start_freq_hz,
                end_freq_hz=tp.incoming.end_freq_hz,
                direction=tp.incoming.direction.value,
                curve=tp.incoming.curve.value,
                resonance=tp.incoming.resonance,
                ffmpeg_expr=tp.incoming.ffmpeg_lowpass_expr(8.0),
            )
        return result

    if start_freq_hz is None or end_freq_hz is None:
        raise ValidationError(
            "custom filter sweep requires start_freq_hz and end_freq_hz",
            details={"start_freq_hz": start_freq_hz, "end_freq_hz": end_freq_hz},
        )
    dir_enum = SweepDirection(direction or "close")
    curve_enum = SweepCurve(curve or "exponential")
    plan = FilterSweepPlan(
        start_freq_hz=start_freq_hz,
        end_freq_hz=end_freq_hz,
        direction=dir_enum,
        curve=curve_enum,
        resonance=resonance or 0.7,
    )
    side = FilterSweepSide(
        start_freq_hz=plan.start_freq_hz,
        end_freq_hz=plan.end_freq_hz,
        direction=plan.direction.value,
        curve=plan.curve.value,
        resonance=plan.resonance,
        ffmpeg_expr=plan.ffmpeg_lowpass_expr(8.0),
    )
    return FilterSweepResult(outgoing=side)
