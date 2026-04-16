"""Yandex Music full-text search tool."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from app.clients.ym.client import YandexMusicClient
from app.controllers.dependencies import get_ym_client
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    ICON_YM,
    TOOL_META,
    ToolCategory,
)
from app.controllers.tools.yandex._constants import MAX_SEARCH_LIMIT
from app.schemas.ym_responses import YMSearchResponse

SearchType = Literal["tracks", "albums", "artists", "playlists", "all"]


@tool(
    title="YM Search",
    tags={ToolCategory.YM.value},
    annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    icons=ICON_YM,
    meta=TOOL_META,
)
async def ym_search(
    query: Annotated[str, Field(description="Search query text")],
    type: Annotated[SearchType, Field(description="Entity type to search")] = "all",
    limit: Annotated[
        int, Field(description="Max results per entity type", ge=1, le=MAX_SEARCH_LIMIT)
    ] = 10,
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
) -> YMSearchResponse:
    """Search Yandex Music by text across tracks, albums, artists, and playlists. Use when discovering titles on YM from a query outside the local library."""
    result = await ym.search(query, type=type, limit=min(limit, MAX_SEARCH_LIMIT))
    return YMSearchResponse(
        query=query,
        type=type,
        tracks=[t.model_dump() for t in result.tracks],
        albums=[a.model_dump() for a in result.albums],
        artists=[a.model_dump() for a in result.artists],
        playlists=[p.model_dump() for p in result.playlists],
    )
