"""Yandex Music full-text search tool."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool

from app.controllers.dependencies import get_ym_client
from app.controllers.tools._shared import ANNOTATIONS_READ_ONLY_OPEN_WORLD, ToolCategory
from app.controllers.tools.yandex._constants import MAX_SEARCH_LIMIT, VALID_SEARCH_TYPES
from app.ym.client import YandexMusicClient


@tool(tags={ToolCategory.YM.value}, annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD)
async def ym_search(
    query: str,
    type: str = "all",
    limit: int = 10,
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
) -> dict[str, Any]:
    """Search Yandex Music for tracks, albums, artists, playlists.

    ``type`` ∈ ``{tracks, albums, artists, playlists, all}``.
    """
    if type not in VALID_SEARCH_TYPES:
        raise ToolError(f"Invalid type: {type}. Valid: {', '.join(sorted(VALID_SEARCH_TYPES))}")

    result = await ym.search(query, type=type, limit=min(limit, MAX_SEARCH_LIMIT))
    return {
        "query": query,
        "type": type,
        "tracks": [t.model_dump() for t in result.tracks],
        "albums": [a.model_dump() for a in result.albums],
        "artists": [a.model_dump() for a in result.artists],
        "playlists": [p.model_dump() for p in result.playlists],
    }
