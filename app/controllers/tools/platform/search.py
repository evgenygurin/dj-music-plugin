"""Platform full-text search tool."""

from typing import Annotated, Literal

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from app.controllers.dependencies.external import get_music_provider
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    ICON_YM,
    TOOL_META,
    ToolCategory,
)
from app.controllers.tools.platform._constants import MAX_SEARCH_LIMIT
from app.providers.protocol import MusicProvider
from app.schemas.platform_responses import PlatformSearchResult

SearchType = Literal["tracks", "albums", "artists", "playlists", "all"]


@tool(
    title="Platform Search",
    tags={ToolCategory.PLATFORM.value},
    annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    icons=ICON_YM,
    meta=TOOL_META,
)
async def search_platform(
    query: Annotated[str, Field(description="Search query text")],
    type: Annotated[SearchType, Field(description="Entity type to search")] = "all",
    limit: Annotated[
        int, Field(description="Max results per entity type", ge=1, le=MAX_SEARCH_LIMIT)
    ] = 10,
    provider: MusicProvider = Depends(get_music_provider),  # noqa: B008
) -> PlatformSearchResult:
    """Search platform catalog by text across tracks, albums, artists, and playlists."""
    result = await provider.search(query, search_type=type, page_size=min(limit, MAX_SEARCH_LIMIT))
    return PlatformSearchResult(
        query=query,
        type=type,
        tracks=[t.model_dump() for t in result.tracks],
        albums=[a.model_dump() for a in result.albums],
        artists=[a.model_dump() for a in result.artists],
        playlists=[p.model_dump() for p in result.playlists],
    )
