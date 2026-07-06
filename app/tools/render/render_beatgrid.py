"""render_beatgrid — kick-phase + QA (phase refine + LUFS gain) for a version."""

from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.render_beatgrid import render_beatgrid_handler
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.render import RenderBeatgridResult
from app.server.di import get_uow
from app.tools.render._shared import render_workspace


@tool(
    name="render_beatgrid",
    tags={"namespace:render", "write"},
    annotations={"readOnlyHint": False, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Compute the beatgrid for a set version: kick-phase detect + sub-beat "
        "phase refine + LUFS level-match. Writes beatgrid.json. Heavy (librosa) "
        "— runs as a background task."
    ),
    meta={"timeout_s": 600.0},
    timeout=600.0,
    task=True,
)
async def render_beatgrid(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    refresh: Annotated[bool, Field(description="Recompute even if cached")] = False,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> RenderBeatgridResult:
    return await render_beatgrid_handler(
        ctx=ctx,
        uow=uow,
        version_id=version_id,
        workspace=render_workspace(version_id),
        refresh=refresh,
    )
