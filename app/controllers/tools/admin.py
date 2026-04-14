"""Admin tools: tool visibility control and platform listing."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.controllers.dependencies import get_track_service
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE,
    ICON_ADMIN,
    TOOL_META,
    ToolCategory,
    map_domain_errors,
)
from app.core.constants import Provider
from app.services.track_service import TrackService

# Categories that can be toggled at runtime. "core", "sets", "admin" are
# always visible, so the unlock controls only the hideable ones.
_TOGGLEABLE_CATEGORIES: frozenset[str] = frozenset(
    {
        ToolCategory.DELIVERY.value,
        ToolCategory.DISCOVERY.value,
        ToolCategory.CURATION.value,
        ToolCategory.SYNC.value,
        ToolCategory.YM.value,
        ToolCategory.AUDIO.value,
        ToolCategory.MEMORY.value,
    }
)


def _resolve_categories(category: str) -> set[str]:
    tags = set(_TOGGLEABLE_CATEGORIES) if category == "all" else {category}
    invalid = tags - _TOGGLEABLE_CATEGORIES
    if invalid:
        raise ToolError(f"Unknown categories: {sorted(invalid)}")
    return tags


def _build_status(ctx: Context) -> dict[str, Any]:
    """Check which toggleable categories are currently enabled/disabled.

    Uses ``ctx.fastmcp`` (the server instance) to inspect the active
    visibility transforms.  Each category is reported as "enabled" or
    "disabled" based on whether the server currently lists tools with
    that tag.
    """
    server = ctx.fastmcp
    # Walk the server's visibility transforms to determine state.
    # Transforms are Visibility objects with .enabled (bool) and .tags/.keys.
    effective: dict[str, str] = {}
    for category in sorted(_TOGGLEABLE_CATEGORIES):
        state = "enabled"
        for transform in server.transforms:
            if type(transform).__name__ != "Visibility":
                continue
            t_tags = getattr(transform, "tags", None) or set()
            if category in t_tags:
                state = "enabled" if getattr(transform, "enabled", True) else "disabled"
        effective[category] = state

    return {
        "action": "status",
        "toggleable_categories": sorted(_TOGGLEABLE_CATEGORIES),
        "effective": effective,
    }


@tool(
    title="Unlock Tools",
    tags={ToolCategory.ADMIN.value},
    annotations=ANNOTATIONS_WRITE,
    icons=ICON_ADMIN,
    meta=TOOL_META,
)
@map_domain_errors
async def unlock_tools(
    action: Annotated[
        Literal["unlock", "lock", "status"],
        Field(description="Operation to perform"),
    ] = "status",
    category: Annotated[
        str | None,
        Field(description="Tool category to toggle, or 'all'"),
    ] = None,
    ctx: Annotated[
        Context | None,
        Field(description="MCP server context; required for status, lock, and unlock"),
    ] = None,
) -> dict[str, Any]:
    """Shows lock state or toggles hideable MCP tool categories via the server. Use when unlocking gated categories (for example delivery or YM) for the current session."""
    if action == "status":
        if ctx is None:
            raise ToolError("Context required for status")
        return _build_status(ctx)

    # action ∈ {unlock, lock}
    if not category:
        raise ToolError(f"Category required for action={action}")
    if ctx is None:
        raise ToolError(f"Context required for {action}")

    tags = _resolve_categories(category)
    server = ctx.fastmcp

    if action == "unlock":
        # Server-level enable → triggers tools/list_changed notification
        server.enable(tags=tags)
        return {"action": "unlocked", "categories": sorted(tags)}

    # lock
    server.disable(tags=tags)
    return {"action": "locked", "categories": sorted(tags)}


@tool(
    title="List Platforms",
    tags={ToolCategory.ADMIN.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_ADMIN,
    meta=TOOL_META,
)
@map_domain_errors
async def list_platforms(
    svc: Annotated[
        TrackService,
        Field(description="Track service for per-platform link counts"),
    ] = Depends(get_track_service),  # noqa: B008
) -> list[dict[str, Any]]:
    """Lists music providers and how many tracks are linked per platform. Use when checking multi-platform coverage or import linkage."""
    db_platforms = await svc.get_platform_counts()
    return [
        {
            "platform": provider.value,
            "linked_tracks": db_platforms.get(provider.value, 0),
            "available": True,
        }
        for provider in Provider
    ]
