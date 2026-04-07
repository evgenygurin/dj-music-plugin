"""Admin tools: tool visibility control and platform listing."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.core.constants import Provider
from app.mcp.dependencies import get_track_service
from app.mcp.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE,
    ToolCategory,
)
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
        ToolCategory.ATOMIC.value,
    }
)


def _resolve_categories(category: str) -> set[str]:
    tags = set(_TOGGLEABLE_CATEGORIES) if category == "all" else {category}
    invalid = tags - _TOGGLEABLE_CATEGORIES
    if invalid:
        raise ToolError(f"Unknown categories: {sorted(invalid)}")
    return tags


@tool(tags={ToolCategory.ADMIN.value}, annotations=ANNOTATIONS_WRITE)
async def unlock_tools(
    action: str = "status",
    category: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Control which tool categories are visible in this session."""
    if action in ("unlock", "lock"):
        if not category:
            raise ToolError(f"Category required for action={action}")
        if ctx is None:
            raise ToolError(f"Context required for {action}")
        tags = _resolve_categories(category)
        if action == "unlock":
            await ctx.enable_components(tags=tags)
            return {"action": "unlocked", "categories": sorted(tags)}
        await ctx.disable_components(tags=tags)
        return {"action": "locked", "categories": sorted(tags)}

    return {"action": "status", "message": "Use unlock/lock with a category"}


@tool(tags={ToolCategory.ADMIN.value}, annotations=ANNOTATIONS_READ_ONLY)
async def list_platforms(
    svc: TrackService = Depends(get_track_service),  # noqa: B008
) -> list[dict[str, Any]]:
    """List available music platforms and linked track counts."""
    db_platforms = await svc.get_platform_counts()
    return [
        {
            "platform": provider.value,
            "linked_tracks": db_platforms.get(provider.value, 0),
            "available": True,
        }
        for provider in Provider
    ]
