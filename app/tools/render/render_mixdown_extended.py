"""render_mixdown_extended — full-DSP beatmatched mixdown.

Same as ``render_mixdown`` plus 24 optional DSP override parameters.
Read current defaults via ``reference://render/settings`` resource.

All DSP params are optional (None = use RenderSettings config default).
"""

from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.render_mixdown_extended import render_mixdown_extended_handler
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.render import RenderMixdownResult
from app.server.di import get_uow
from app.tools.render._shared import render_timestamp, render_workspace


@tool(
    name="render_mixdown_extended",
    tags={"namespace:render", "write"},
    annotations={"readOnlyHint": False, "idempotentHint": False, "openWorldHint": False},
    description=(
        "Render the continuous beatmatched mix with FULL per-render DSP control. "
        "Same engine as render_mixdown plus 24 optional DSP override parameters "
        "(HPF, pre-compressor, glue compressor, master EQ, limiter, crossover freqs, "
        "dynaudnorm). All DSP params default to None = use RenderSettings config default. "
        "Read current defaults via reference://render/settings resource."
    ),
    meta={"timeout_s": 1800.0},
    timeout=1800.0,
    task=True,
)
async def render_mixdown_extended(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    out_name: Annotated[str | None, Field(description="Output filename (default MIX.mp3)")] = None,
    transition_bars: Annotated[
        int | None, Field(ge=1, description="Override transition length")
    ] = None,
    body_bars: Annotated[
        int | None, Field(ge=1, description="Override per-track solo length")
    ] = None,
    refresh_grid: Annotated[bool, Field(description="Recompute the beatgrid first")] = False,
    stem: Annotated[
        bool, Field(description="Demucs stem render (default); False = classic EQ bass-swap")
    ] = True,
    subgenre: Annotated[
        str | None,
        Field(
            description="Subgenre preset: industrial_techno, dub_techno, hard_techno, hypnotic_techno, peak_time_techno, driving_techno, acid_techno"
        ),
    ] = None,
    filter_sweep: Annotated[
        str | None,
        Field(
            description="Filter sweep preset: classic_lowpass, acid_squelch, industrial_cut, hypnotic_wash, dub_echo_sweep"
        ),
    ] = None,
    echo: Annotated[
        str | None,
        Field(
            description="Echo preset: techno_standard, vocal_throw, industrial_stutter, dub_space, acid_bounce"
        ),
    ] = None,
    crossfade_curve_out: Annotated[
        str,
        Field(description="Crossfade curve for outgoing track: tri, exp, log, squ, sin, nofade"),
    ] = "tri",
    crossfade_curve_in: Annotated[
        str,
        Field(description="Crossfade curve for incoming track: tri, exp, log, squ, sin, nofade"),
    ] = "exp",
    reverb: Annotated[
        str | None,
        Field(
            description="Reverb preset: techno_hall, techno_cathedral, industrial_warehouse, dub_plate, minimal_room"
        ),
    ] = None,
    reverb_mix: Annotated[float, Field(ge=0.0, le=1.0, description="Reverb wet/dry ratio")] = 0.25,
    hpf_cutoff_hz: Annotated[
        float | None, Field(gt=0, description="Subsonic highpass filter cutoff. Default 30.0")
    ] = None,
    per_track_eq_mid_cut_db: Annotated[
        float | None, Field(le=0, description="300-500Hz mid cut for all tracks. Default -1.0")
    ] = None,
    per_track_eq_bright_boost_db: Annotated[
        float | None, Field(ge=0, description="8-12kHz boost for dark tracks. Default 1.5")
    ] = None,
    pre_comp_threshold_db: Annotated[
        float | None, Field(description="Pre-compressor threshold. Default -18.0")
    ] = None,
    pre_comp_ratio: Annotated[
        float | None, Field(gt=1, description="Pre-compressor ratio. Default 3.0")
    ] = None,
    pre_comp_attack_ms: Annotated[
        float | None, Field(gt=0, description="Pre-compressor attack (ms). Default 10.0")
    ] = None,
    pre_comp_release_ms: Annotated[
        float | None, Field(gt=0, description="Pre-compressor release (ms). Default 80.0")
    ] = None,
    glue_comp_threshold_db: Annotated[
        float | None, Field(description="Glue compressor threshold. Default -14.0")
    ] = None,
    glue_comp_ratio: Annotated[
        float | None, Field(gt=1, description="Glue compressor ratio. Default 3.0")
    ] = None,
    glue_comp_attack_ms: Annotated[
        float | None, Field(gt=0, description="Glue compressor attack (ms). Default 30.0")
    ] = None,
    glue_comp_release_ms: Annotated[
        float | None, Field(gt=0, description="Glue compressor release (ms). Default 150.0")
    ] = None,
    master_eq_air_boost_db: Annotated[
        float | None, Field(ge=0, description="10-12kHz high shelf boost. Default 1.5")
    ] = None,
    master_eq_mud_cut_db: Annotated[
        float | None, Field(le=0, description="200-400Hz mud cut. Default -1.0")
    ] = None,
    master_eq_sub_boost_db: Annotated[
        float | None, Field(ge=0, description="60-80Hz sub weight boost. Default 0.5")
    ] = None,
    limiter_attack_ms: Annotated[
        float | None, Field(gt=0, description="alimiter attack (ms). Default 10.0")
    ] = None,
    limiter_release_ms: Annotated[
        float | None, Field(gt=0, description="alimiter release (ms). Default 30.0")
    ] = None,
    limiter_ceiling: Annotated[
        float | None, Field(gt=0, le=1.0, description="alimiter limit. Default 0.85")
    ] = None,
    dynaudnorm_maxgain: Annotated[
        float | None, Field(ge=0, description="dynaudnorm maxgain. Default 2.0")
    ] = None,
    xsplit_low_hz: Annotated[
        int | None, Field(gt=0, description="Low/mid crossover (Hz). Default 250")
    ] = None,
    xsplit_high_hz: Annotated[
        int | None, Field(gt=0, description="Mid/high crossover (Hz). Default 4000")
    ] = None,
    eq_phase_1_ratio: Annotated[
        float | None,
        Field(gt=0, le=1.0, description="Fraction of transition for HIGH phase. Default 0.40"),
    ] = None,
    eq_phase_2_ratio: Annotated[
        float | None,
        Field(gt=0, le=1.0, description="Fraction of transition for MID phase. Default 0.70"),
    ] = None,
    low_swap_beats: Annotated[
        float | None, Field(gt=0, description="Low-band crossfade window (beats). Default 1.0")
    ] = None,
    outro_fade_bars: Annotated[
        int | None, Field(gt=0, description="End-of-mix fade length. Default 12")
    ] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> RenderMixdownResult:
    return await render_mixdown_extended_handler(
        ctx=ctx,
        uow=uow,
        version_id=version_id,
        workspace=render_workspace(version_id),
        timestamp=render_timestamp(),
        out_name=out_name,
        transition_bars=transition_bars,
        body_bars=body_bars,
        refresh_grid=refresh_grid,
        stem=stem,
        subgenre=subgenre,
        filter_sweep=filter_sweep,
        echo=echo,
        crossfade_curve_out=crossfade_curve_out,
        crossfade_curve_in=crossfade_curve_in,
        reverb=reverb,
        reverb_mix=reverb_mix,
        hpf_cutoff_hz=hpf_cutoff_hz,
        per_track_eq_mid_cut_db=per_track_eq_mid_cut_db,
        per_track_eq_bright_boost_db=per_track_eq_bright_boost_db,
        pre_comp_threshold_db=pre_comp_threshold_db,
        pre_comp_ratio=pre_comp_ratio,
        pre_comp_attack_ms=pre_comp_attack_ms,
        pre_comp_release_ms=pre_comp_release_ms,
        glue_comp_threshold_db=glue_comp_threshold_db,
        glue_comp_ratio=glue_comp_ratio,
        glue_comp_attack_ms=glue_comp_attack_ms,
        glue_comp_release_ms=glue_comp_release_ms,
        master_eq_air_boost_db=master_eq_air_boost_db,
        master_eq_mud_cut_db=master_eq_mud_cut_db,
        master_eq_sub_boost_db=master_eq_sub_boost_db,
        limiter_attack_ms=limiter_attack_ms,
        limiter_release_ms=limiter_release_ms,
        limiter_ceiling=limiter_ceiling,
        dynaudnorm_maxgain=dynaudnorm_maxgain,
        xsplit_low_hz=xsplit_low_hz,
        xsplit_high_hz=xsplit_high_hz,
        eq_phase_1_ratio=eq_phase_1_ratio,
        eq_phase_2_ratio=eq_phase_2_ratio,
        low_swap_beats=low_swap_beats,
        outro_fade_bars=outro_fade_bars,
    )
