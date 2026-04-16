"""Yandex Music track and artist-track tools."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from pydantic import Field

from app.controllers.dependencies.external import get_music_provider
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    ICON_YM,
    TOOL_META,
    ToolCategory,
)
from app.controllers.tools.yandex._constants import MAX_BATCH_TRACKS, MAX_SEARCH_LIMIT
from app.core.utils.parsing import ensure_list
from app.providers.protocol import MusicProvider
from app.schemas.ym_responses import YMArtistTrackItem, YMArtistTracksPage, YMTrackBatch

ArtistSortBy = Literal["date", "popularity"]
_PAGE_SIZE = 20


@tool(
    title="YM Get Tracks",
    tags={ToolCategory.YM.value},
    annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    icons=ICON_YM,
    meta=TOOL_META,
)
async def ym_get_tracks(
    track_ids: Annotated[
        str | list[str],
        Field(
            description="YM track ID or comma-separated IDs (e.g. '12345' or ['12345','67890'])"
        ),
    ],
    fields: Annotated[
        str,
        Field(
            description="Comma-separated field names to return, or 'all' for full data",
            examples=["id,title,artists,albums,duration_ms", "all"],
        ),
    ] = "id,title,artists,albums,duration_ms",
    provider: MusicProvider = Depends(get_music_provider),  # noqa: B008
) -> YMTrackBatch:
    """Batch-load tracks from Yandex Music by ID with optional field projection. Use when resolving IDs from search or albums into titles, artists, and durations."""
    ids = ensure_list(track_ids)
    if not ids:
        raise ToolError("track_ids required")
    if len(ids) > MAX_BATCH_TRACKS:
        raise ToolError(f"Maximum {MAX_BATCH_TRACKS} track IDs per request")

    tracks = await provider.get_tracks(ids)
    if fields == "all":
        tracks_data = [t.model_dump() for t in tracks]
    else:
        wanted = {f.strip() for f in fields.split(",")}
        tracks_data = [{k: v for k, v in t.model_dump().items() if k in wanted} for t in tracks]
    return YMTrackBatch(count=len(tracks_data), tracks=tracks_data)


@tool(
    title="YM Artist Tracks",
    tags={ToolCategory.YM.value},
    annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    icons=ICON_YM,
    meta=TOOL_META,
)
async def ym_artist_tracks(
    artist_id: Annotated[str, Field(description="YM artist ID (string)")],
    offset: Annotated[int, Field(description="Number of tracks to skip", ge=0)] = 0,
    limit: Annotated[int, Field(description="Max tracks to return", ge=1, le=100)] = _PAGE_SIZE,
    sort_by: Annotated[ArtistSortBy, Field(description="Sort order")] = "date",
    provider: MusicProvider = Depends(get_music_provider),  # noqa: B008
) -> YMArtistTracksPage:
    """Return a paginated slice of tracks for a Yandex Music artist. Use when browsing an artist catalog or paging through their releases on YM."""
    page = offset // limit
    tracks = await provider.get_artist_tracks(artist_id, page=page)

    page_slice = tracks[offset % limit :] if offset % limit else tracks
    page_slice = page_slice[:limit]

    return YMArtistTracksPage(
        artist_id=artist_id,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        count=len(page_slice),
        tracks=[
            YMArtistTrackItem(
                id=t.id,
                title=t.title,
                duration_ms=t.duration_ms,
                albums=[{"id": t.album_id, "title": t.album_title, "genre": t.album_genre}]
                if t.album_id
                else [],
            )
            for t in page_slice
        ],
        has_next=len(tracks) >= MAX_SEARCH_LIMIT,
    )
