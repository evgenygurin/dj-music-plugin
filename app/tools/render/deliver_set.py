"""deliver_set — build a portable delivery bundle for a set version."""

from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.deliver_set import deliver_set_handler
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.delivery import DeliverSetResult
from app.server.di import get_uow


@tool(
    name="deliver_set",
    tags={"namespace:render", "write"},
    annotations={"readOnlyHint": False, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Build a portable delivery bundle for a set version: copy source audio files, "
        "generate M3U8 playlist, rekordbox XML metadata, JSON guide, cheatsheet, "
        "and the rendered MIX.mp3. All outputs go to "
        "<DeliverySettings.output_dir>/deliver/v{version_id}/."
    ),
    meta={"timeout_s": 60.0},
    timeout=60.0,
)
async def deliver_set(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    out_dir: Annotated[
        str | None, Field(description="Override output directory (default: auto)")
    ] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> DeliverSetResult:
    return await deliver_set_handler(
        ctx=ctx,
        uow=uow,
        version_id=version_id,
        out_dir=out_dir,
    )
