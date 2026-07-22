"""render_beatgrid handler: thin entry to BeatgridProvider.compute."""

from __future__ import annotations

from typing import Any

from app.handlers._orchestrator.beatgrid_provider import BeatgridProvider
from app.schemas.render import RenderBeatgridResult


async def render_beatgrid_handler(
    *, ctx: Any, uow: Any, version_id: int, workspace: str, refresh: bool = False
) -> RenderBeatgridResult:
    return await BeatgridProvider().compute(ctx, uow, version_id, workspace, refresh=refresh)
