"""Session-scoped set draft resource (session://set-draft)."""

from __future__ import annotations

from fastmcp.dependencies import CurrentContext
from fastmcp.resources import ResourceResult, resource
from fastmcp.server.context import Context

from app.controllers.resources._shared import json_resource
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ICON_SETS,
    RESOURCE_META,
    RESOURCE_VERSION,
)


@resource(
    uri="session://set-draft",
    name="Set Draft",
    title="Current Set Draft",
    description=(
        "Read the current session-scoped set draft. "
        "Returns {} if no draft exists. Updated by update_set_draft."
    ),
    mime_type="application/json",
    tags={"sets"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def get_set_draft(ctx: Context = CurrentContext()) -> ResourceResult:  # noqa: B008
    """Return the current set draft stored in session state."""
    return json_resource(await ctx.get_state("set_draft") or {})
