"""Admin tools: tool visibility control and platform listing."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.core.constants import Provider
from app.mcp.dependencies import get_track_service
from app.services.track_service import TrackService

_ALL_CATEGORIES = frozenset({"delivery", "discovery", "curation", "sync", "ym", "audio", "atomic"})


@tool(tags={"admin"}, annotations={"readOnlyHint": False})
async def unlock_tools(
    action: str = "status",
    category: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Control which tool categories are visible in this session."""
    if action == "unlock" and category:
        tags = {category} if category != "all" else set(_ALL_CATEGORIES)
        invalid = tags - _ALL_CATEGORIES
        if invalid:
            raise ToolError(f"Unknown categories: {sorted(invalid)}")
        if ctx is None:
            raise ToolError("Context required for unlock")
        await ctx.enable_components(tags=tags)
        return {"action": "unlocked", "categories": sorted(tags)}

    elif action == "lock" and category:
        tags = {category} if category != "all" else set(_ALL_CATEGORIES)
        invalid = tags - _ALL_CATEGORIES
        if invalid:
            raise ToolError(f"Unknown categories: {sorted(invalid)}")
        if ctx is None:
            raise ToolError("Context required for lock")
        await ctx.disable_components(tags=tags)
        return {"action": "locked", "categories": sorted(tags)}

    return {"action": "status", "message": "Use unlock/lock with a category"}


@tool(tags={"admin"}, annotations={"readOnlyHint": True})
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
