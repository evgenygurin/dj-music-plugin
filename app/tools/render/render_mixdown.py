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
        "Render the continuous beatmatched mix (rubberband→target BPM, 32-bar "
        "EQ bass-swap transitions, limiter) for a set version. Auto-runs the "
        "beatgrid if missing. Heavy (ffmpeg) — background task."
    ),
    meta={"timeout_s": 900.0},
    timeout=900.0,
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
    )
