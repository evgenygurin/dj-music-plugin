"""render_verify — run DJ-adapted mix verification checks on a set version."""

from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.render_verify import render_verify_handler
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.render import RenderVerifyResult
from app.server.di import get_uow


@tool(
    name="render_verify",
    tags={"namespace:render", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Run DJ-adapted mix verification on a set version: 5 pre-render checks "
        "(source duration, BPM reliability, trim bounds, boundary alignment, "
        "timeline) and 9 post-render checks (output duration, level jumps, "
        "clipping, dropouts, loudness consistency, low-band holes, stereo "
        "balance, RMS jumps, energy slope). "
        "Auto-runs the beatgrid if missing."
    ),
    meta={"timeout_s": 120.0},
    timeout=120.0,
)
async def render_verify(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    skip_post: Annotated[
        bool, Field(description="Skip post-render checks (output file not required)")
    ] = False,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> RenderVerifyResult:
    return await render_verify_handler(
        ctx=ctx,
        uow=uow,
        version_id=version_id,
        skip_post=skip_post,
    )
