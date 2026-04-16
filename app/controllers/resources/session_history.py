"""Session tool call history resource."""

from __future__ import annotations

from fastmcp.dependencies import CurrentContext
from fastmcp.resources import ResourceResult, resource
from fastmcp.server.context import Context

from app.controllers.resources._shared import json_resource
from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ICON_ADMIN,
    RESOURCE_META,
    RESOURCE_VERSION,
)


@resource(
    uri="session://tool-history",
    name="Tool Call History",
    title="Session Tool Call History",
    description=(
        "Recent tool calls in the current session. "
        "Shows last 20 calls with tool name, timestamp, and status."
    ),
    tags={"admin"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_ADMIN,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def tool_history(ctx: Context = CurrentContext()) -> ResourceResult:  # noqa: B008
    """Return recent tool calls from session state."""
    history = await ctx.get_state("tool_history") or []
    return json_resource({"calls": history[-20:], "total": len(history)})
