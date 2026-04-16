"""Yandex Music album tools."""

from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.exceptions import NotFoundError as FastMCPNotFoundError
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
from app.providers.protocol import MusicProvider
from app.schemas.ym_responses import YMAlbumResponse


@tool(
    title="YM Get Album",
    tags={ToolCategory.YM.value},
    annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    icons=ICON_YM,
    meta=TOOL_META,
)
async def ym_get_album(
    album_id: Annotated[str, Field(description="YM album ID (string)")],
    include_tracks: Annotated[
        bool, Field(description="Include track listing in response")
    ] = False,
    provider: MusicProvider = Depends(get_music_provider),  # noqa: B008
) -> YMAlbumResponse:
    """Fetch album metadata from Yandex Music, optionally including tracks. Use when resolving an album ID or showing album details from YM."""
    if not album_id or not str(album_id).strip():
        raise ToolError("album_id is required")

    album = await provider.get_album(album_id, with_tracks=include_tracks)

    if album is None:
        raise FastMCPNotFoundError(f"Album not found: {album_id}")

    if not album.title and not album.artists and not album.tracks:
        raise FastMCPNotFoundError(f"Album not found: {album_id}")

    return YMAlbumResponse(album_id=album_id, album=album.model_dump())
