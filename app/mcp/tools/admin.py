"""Admin tools: tool visibility control and platform listing."""

from __future__ import annotations

from fastmcp.server.context import Context
from sqlalchemy import func, select

from app.core.constants import Provider
from app.models.track import TrackExternalId
from app.server import mcp

_ALL_CATEGORIES = frozenset({"delivery", "discovery", "curation", "sync", "ym", "audio"})


async def _get_session(ctx: Context | None):  # type: ignore[no-untyped-def]
    """Get async session from lifespan context."""
    if ctx is None:
        raise RuntimeError("Context required")
    factory = ctx.lifespan_context["db_session_factory"]
    return factory()


@mcp.tool(tags={"admin"})
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
            if ctx:
                await ctx.warning(f"Unknown categories requested: {sorted(invalid)}")
            return {"error": f"Unknown categories: {sorted(invalid)}"}
        await ctx.enable_components(tags=tags)
        if ctx:
            await ctx.info(
                f"Unlocked tool categories: {', '.join(sorted(tags))}",
                extra={"action": "unlock", "categories": sorted(tags)}
            )
        return {"action": "unlocked", "categories": sorted(tags)}

    elif action == "lock" and category:
        tags = {category} if category != "all" else set(_ALL_CATEGORIES)
        invalid = tags - _ALL_CATEGORIES
        if invalid:
            if ctx:
                await ctx.warning(f"Unknown categories requested: {sorted(invalid)}")
            return {"error": f"Unknown categories: {sorted(invalid)}"}
        await ctx.disable_components(tags=tags)
        if ctx:
            await ctx.info(
                f"Locked tool categories: {', '.join(sorted(tags))}",
                extra={"action": "lock", "categories": sorted(tags)}
            )
        return {"action": "locked", "categories": sorted(tags)}

    if ctx:
        await ctx.debug("Returning visibility status")
    return {"action": "status", "message": "Use unlock/lock with a category"}


@mcp.tool(tags={"admin"}, annotations={"readOnlyHint": True})
async def list_platforms(ctx: Context | None = None) -> list[dict]:
    """List available music platforms and linked track counts."""
    if ctx:
        await ctx.debug("Querying platform statistics")
    
    async with await _get_session(ctx) as session:
        stmt = select(
            TrackExternalId.platform,
            func.count(TrackExternalId.id).label("track_count"),
        ).group_by(TrackExternalId.platform)
        result = await session.execute(stmt)
        db_platforms = {row.platform: row.track_count for row in result.all()}

    platforms = []
    total_linked = 0
    for provider in Provider:
        count = db_platforms.get(provider.value, 0)
        total_linked += count
        platforms.append(
            {
                "platform": provider.value,
                "linked_tracks": count,
                "available": True,
            }
        )
    
    if ctx:
        await ctx.info(
            f"Found {len(platforms)} platforms with {total_linked} total linked tracks",
            extra={"platform_count": len(platforms), "total_linked": total_linked}
        )
    
    return platforms
