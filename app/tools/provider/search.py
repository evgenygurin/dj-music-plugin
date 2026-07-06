"""provider_search — catalog search against any registered provider."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.registry.provider import ProviderRegistry
from app.schemas.provider_dto import ProviderSearchResult
from app.server.di import get_provider_registry
from app.shared.errors import ValidationError


@tool(
    name="provider_search",
    tags={"namespace:provider:read", "read"},
    annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True},
    description=("Search external platform catalog. type=tracks|albums|artists|playlists|all."),
    meta={"timeout_s": 30.0},
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
    # Audit iter 5: empty query leaked the raw asyncpg/YM-client error
    # ``'str' object has no attribute 'get'`` from the adapter parsing
    # an empty response. Reject up front with a typed error.
    if not query or not query.strip():
        raise ValidationError("query must not be empty or whitespace-only")
    adapter = registry.get(provider)
    raw = await adapter.search(query, type=type, limit=limit)
    # Normalize: for type=tracks, raw["tracks"]["results"] is the list.
    if type == "all":
        # Audit iter 20 (T-21): ``type='all'`` previously read
        # ``raw.get('results')`` which doesn't exist - YM (and most
        # providers) return a sectioned response
        # ``{tracks: {results, total}, albums: {results, total}, ...}``.
        # Aggregate items across every section, tagging each with its
        # ``_section`` so callers can disambiguate.
        items: list[dict[str, Any]] = []
        total = 0
        for section_name, section in (raw or {}).items():
            if not isinstance(section, dict):
                continue
            section_items = section.get("results") or []
            if not isinstance(section_items, list):
                continue
            for it in section_items:
                if isinstance(it, dict):
                    tagged = dict(it)
                    tagged.setdefault("_section", section_name)
                    items.append(tagged)
            section_total = section.get("total")
            if isinstance(section_total, int):
                total += section_total
        return ProviderSearchResult(
            provider=provider, query=query, type=type, total=total, items=items
        )

    section = raw.get(type, {})
    items = section.get("results", []) if isinstance(section, dict) else []
    total = int(section.get("total", len(items))) if isinstance(section, dict) else 0
    return ProviderSearchResult(
        provider=provider, query=query, type=type, total=total, items=items
    )
