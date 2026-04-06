"""Search and filter tools: cross-entity text search + parametric track filter.

Thin wrappers calling SearchService via Depends().
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.mcp.dependencies import get_search_service
from app.services.search_service import SearchService


@tool(tags={"core"}, annotations={"readOnlyHint": True})
async def search(
    query: str,
    entity: str = "all",
    limit: int = 10,
    svc: SearchService = Depends(get_search_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search across tracks, artists, playlists, and sets by text query."""
    if not query or not query.strip():
        raise ToolError("Query must not be empty")
    return await svc.search(query=query, entity=entity, limit=limit)


@tool(tags={"core"}, annotations={"readOnlyHint": True})
async def filter_tracks(
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    key: str | None = None,
    key_compatible: str | None = None,
    energy_min: float | None = None,
    energy_max: float | None = None,
    has_features: bool | None = None,
    exclude_set_id: int | None = None,
    sort_by: str = "bpm",
    limit: int = 20,
    cursor: str | None = None,
    svc: SearchService = Depends(get_search_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Filter tracks by audio features: BPM, key, energy, mood."""
    page = await svc.filter_tracks(
        bpm_min=bpm_min,
        bpm_max=bpm_max,
        key=key,
        key_compatible=key_compatible,
        energy_min=energy_min,
        energy_max=energy_max,
        has_features=has_features,
        exclude_set_id=exclude_set_id,
        sort_by=sort_by,
        limit=limit,
        cursor=cursor,
    )
    return {
        "items": [
            {"id": t.id, "title": t.title, "duration_ms": t.duration_ms} for t in page.items
        ],
        "next_cursor": page.next_cursor,
        "total": page.total,
    }
