"""Search tool: cross-entity text search.

Thin wrapper calling :class:`SearchService` via ``Depends()``.
"""

from typing import Annotated, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.controllers.dependencies import get_search_service
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ICON_SEARCH,
    TOOL_META,
    ToolCategory,
    map_domain_errors,
)
from app.schemas.tool_output import SearchLibraryResult
from app.services.search_service import SearchService

SearchEntity = Literal["all", "tracks", "artists", "playlists", "sets"]


@tool(
    title="Search Library",
    tags={ToolCategory.CORE.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SEARCH,
    meta=TOOL_META,
)
@map_domain_errors
async def search_library(
    query: Annotated[str, Field(description="Search text")],
    entity: Annotated[
        SearchEntity,
        Field(
            description=(
                "Which catalog slice to search: all | tracks | artists | playlists | sets. "
                "Use plural **tracks**, not `track`."
            ),
        ),
    ] = "all",
    limit: Annotated[int, Field(description="Max results", ge=1, le=50)] = 10,
    svc: SearchService = Depends(get_search_service),  # noqa: B008
    ctx: Context = CurrentContext(),  # noqa: B008
) -> SearchLibraryResult:
    """Runs a text search across tracks, artists, playlists, and sets. Use when you know a fragment of a title or name but not the exact ID."""
    if not query or not query.strip():
        raise ToolError("Query must not be empty")
    raw = await svc.search(query=query, entity=entity, limit=limit)
    return SearchLibraryResult.model_validate(raw)
