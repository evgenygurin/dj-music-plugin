"""render_mixdown — beatmatch + EQ bass-swap render to one continuous MP3."""

from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.render_mixdown import render_mixdown_handler
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.render import RenderMixdownResult
from app.server.di import get_uow
from app.tools.render._shared import render_timestamp, render_workspace


@tool(
    name="render_mixdown",
    tags={"namespace:render", "write"},
    annotations={"readOnlyHint": False, "idempotentHint": False, "openWorldHint": False},
    description=(
        "Render the continuous beatmatched mix (rubberband→target BPM, "
        "per-stem transitions, limiter) for a set version. Default: demucs "
        "4-stem multi-deck (clean bass swap, driving drums, gradual "
        "harmonics/vocals). stem=False uses the classic 3-band EQ bass-swap. "
        "Auto-runs the beatgrid if missing; falls back to classic when demucs "
        "is unavailable. Heavy (ffmpeg + demucs) — background task."
    ),
    meta={"timeout_s": 1800.0},
    timeout=1800.0,
    task=True,
)
async def render_mixdown(
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
    reverb_mix: Annotated[
        float,
        Field(ge=0.0, le=1.0, description="Reverb wet/dry ratio"),
    ] = 0.25,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> RenderMixdownResult:
    return await render_mixdown_handler(
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
    )
