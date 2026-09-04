"""render_validate_grid — post-render grid-alignment QA for a version.

Client usage (FastMCP v3 structured output):
    res = await client.call_tool("render_validate_grid", {"version_id": 248})
    # res.data is a hydrated GridCheckResult (Pydantic), not JSON-serializable
    # via stdlib json directly. Use one of:
    #   res.data.model_dump()  # Pydantic → dict
    #   res.structured_content  # raw dict from server
    #   res.content[0].text    # JSON string
    # or helper: from app.shared.json_utils import pydantic_json_dumps
    #   pydantic_json_dumps(res.data)
See https://github.com/prefecthq/fastmcp/blob/main/docs/clients/tools.mdx
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.render_validate_grid import render_validate_grid_handler
from app.schemas.render import GridCheckResult
from app.server.di import get_uow
from app.shared.errors import ValidationError
from app.tools.render._shared import render_mix_path, render_workspace


@tool(
    name="render_validate_grid",
    tags={"namespace:render", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Validate a rendered mix's grid alignment: measures each track body's "
        "BPM in the mix vs target_bpm (proves rubberband honored the beatgrid "
        "tempo_ratio) and flags pre-render stored-BPM vs measured-BPM drift. "
        "Thresholds: |dev|<=0.5 ok, 0.5-1.0 warn, >1.0 fail. Writes "
        "grid_check.json. Heavy (librosa) — background task. Requires a "
        "rendered mix (run render_mixdown first)."
    ),
    meta={"timeout_s": 900.0},
    timeout=900.0,
    task=True,
)
async def render_validate_grid(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    mix_path: Annotated[
        str | None, Field(description="Explicit mix path (default workspace MIX.mp3)")
    ] = None,
    uow: Any = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> GridCheckResult:
    path = mix_path or render_mix_path(version_id)
    if not Path(path).exists():
        raise ValidationError(f"no rendered mix at {path} — run render_mixdown first")

    result = await render_validate_grid_handler(
        ctx=ctx,
        uow=uow,
        version_id=version_id,
        workspace=render_workspace(version_id),
        mix_path=path,
    )
    # FastMCP Client exposes .data as the Pydantic model and .structured_content
    # as the raw dict. Returning a BaseModel is correct for schema, but
    # client-side json.dumps(model) fails (Root/BaseModel not JSON serializable).
    # Callers should use res.data.model_dump() or res.structured_content.
    # We return the model — FastMCP handles structured_content — but ensure
    # the model is JSON-serializable via mode='json' for any direct dumps.
    return result
