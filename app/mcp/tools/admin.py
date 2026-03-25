"""Admin tools: tool visibility control and platform listing."""

from __future__ import annotations

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import Provider
from app.mcp.dependencies import get_db_session
from app.models.track import TrackExternalId

_ALL_CATEGORIES = frozenset({"delivery", "discovery", "curation", "sync", "ym", "audio", "atomic"})


@tool(tags={"admin"})
async def unlock_tools(
    action: str = "status",
    category: str | None = None,
    ctx: Context | None = None,
) -> dict:
    """Control which tool categories are visible in this session."""
    if action == "unlock" and category:
        tags = {category} if category != "all" else set(_ALL_CATEGORIES)
        invalid = tags - _ALL_CATEGORIES
        if invalid:
            raise ToolError(f"Unknown categories: {sorted(invalid)}")
        await ctx.enable_components(tags=tags)
        return {"action": "unlocked", "categories": sorted(tags)}

    elif action == "lock" and category:
        tags = {category} if category != "all" else set(_ALL_CATEGORIES)
        invalid = tags - _ALL_CATEGORIES
        if invalid:
            raise ToolError(f"Unknown categories: {sorted(invalid)}")
        await ctx.disable_components(tags=tags)
        return {"action": "locked", "categories": sorted(tags)}

    return {"action": "status", "message": "Use unlock/lock with a category"}


@tool(tags={"admin"}, annotations={"readOnlyHint": True})
async def list_platforms(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> list[dict]:
    """List available music platforms and linked track counts."""
    stmt = select(
        TrackExternalId.platform,
        func.count(TrackExternalId.id).label("track_count"),
    ).group_by(TrackExternalId.platform)
    result = await session.execute(stmt)
    db_platforms = {row.platform: row.track_count for row in result.all()}

    return [
        {
            "platform": provider.value,
            "linked_tracks": db_platforms.get(provider.value, 0),
            "available": True,
        }
        for provider in Provider
    ]

