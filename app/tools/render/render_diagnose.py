"""render_diagnose — scan + per-4s defect sweep of a rendered mix."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastmcp.dependencies import CurrentContext
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.render_diagnose import render_diagnose_handler
from app.schemas.render import RenderDiagnosticsResult
from app.shared.errors import ValidationError
from app.tools.render._shared import render_workspace


@tool(
    name="render_diagnose",
    tags={"namespace:render", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Scan + per-4s librosa defect sweep of a rendered mix (level jumps, "
        "dropouts, bass-thin). Heavy — background task. Pass version_id to "
        "diagnose that version's MIX.mp3, or an explicit mix_path."
    ),
    meta={"timeout_s": 900.0},
    timeout=900.0,
    task=True,
)
async def render_diagnose(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    mix_path: Annotated[
        str | None, Field(description="Explicit mix path (default workspace MIX.mp3)")
    ] = None,
    ctx: Context = CurrentContext(),
) -> RenderDiagnosticsResult:
    ws = render_workspace(version_id)
    path = mix_path or str(Path(ws) / "MIX.mp3")
    if not Path(path).exists():
        raise ValidationError(f"no rendered mix at {path} — run render_mixdown first")
    return await render_diagnose_handler(
        ctx=ctx,
        job_id=f"v{version_id}",
        mix_path=path,
        workspace=ws,
    )
