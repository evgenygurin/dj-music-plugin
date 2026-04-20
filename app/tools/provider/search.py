"""provider_search — catalog search against any registered provider."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.registry.provider import ProviderRegistry
from app.schemas.provider_dto import ProviderSearchResult
from app.server.di import get_provider_registry


@tool(
    name="provider_search",
    tags={"namespace:provider:read", "read"},
    annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True},
    description=("Search external platform catalog. type=tracks|albums|artists|playlists|all."),
    timeout=30.0,
)
async def provider_search(
    provider: Annotated[str, Field(description="Provider name")],
    query: Annotated[str, Field(description="Free-text query")],
    type: Annotated[
        Literal["tracks", "albums", "artists", "playlists", "all"],
        Field(description="Entity type to search"),
    ] = "tracks",
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
    registry: ProviderRegistry = Depends(get_provider_registry),
    ctx: Context = CurrentContext(),
) -> ProviderSearchResult:
    adapter = registry.get(provider)
    raw = await adapter.search(query, type=type, limit=limit)
    # Normalize: for type=tracks, raw["tracks"]["results"] is the list.
    section = raw.get(type, {}) if type != "all" else raw
    items = section.get("results", []) if isinstance(section, dict) else []
    total = int(section.get("total", len(items))) if isinstance(section, dict) else 0
    return ProviderSearchResult(
        provider=provider, query=query, type=type, total=total, items=items
    )
