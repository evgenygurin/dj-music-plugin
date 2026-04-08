"""Yandex Music track and artist-track tools."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool

from app.core.parsing import ensure_list
from app.mcp.dependencies import get_ym_client
from app.mcp.tools._shared import ANNOTATIONS_READ_ONLY_OPEN_WORLD, ToolCategory
from app.mcp.tools.yandex._constants import (
    MAX_BATCH_TRACKS,
    MAX_SEARCH_LIMIT,
    VALID_ARTIST_SORTS,
)
from app.ym.client import YandexMusicClient


@tool(tags={ToolCategory.YM.value}, annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD)
async def ym_get_tracks(
    track_ids: Any = None,
    fields: str = "id,title,artists,albums,duration_ms",
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
) -> dict[str, Any]:
    """Batch get tracks from Yandex Music by IDs (up to 100)."""
    ids = ensure_list(track_ids)
    if not ids:
        raise ToolError("track_ids required")
    if len(ids) > MAX_BATCH_TRACKS:
        raise ToolError(f"Maximum {MAX_BATCH_TRACKS} track IDs per request")

    tracks = await ym.get_tracks(ids)
    if fields == "all":
        tracks_data = [t.model_dump() for t in tracks]
    else:
        wanted = {f.strip() for f in fields.split(",")}
        tracks_data = [{k: v for k, v in t.model_dump().items() if k in wanted} for t in tracks]
    return {"count": len(tracks_data), "tracks": tracks_data}


@tool(tags={ToolCategory.YM.value}, annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD)
async def ym_artist_tracks(
    artist_id: str,
    page: int = 0,
    sort_by: str = "date",
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
) -> dict[str, Any]:
    """Get paginated tracks by artist from Yandex Music.

    ``sort_by`` ∈ ``{date, popularity}``.
    """
    if sort_by not in VALID_ARTIST_SORTS:
        raise ToolError(
            f"Invalid sort_by: {sort_by}. Valid: {', '.join(sorted(VALID_ARTIST_SORTS))}"
        )

    tracks = await ym.get_artist_tracks(artist_id, page=page)
    return {
        "artist_id": artist_id,
        "page": page,
        "sort_by": sort_by,
        "count": len(tracks),
        "tracks": [
            {"id": t.id, "title": t.title, "duration_ms": t.duration_ms, "albums": t.albums}
            for t in tracks
        ],
        "has_next": len(tracks) >= MAX_SEARCH_LIMIT,
    }
