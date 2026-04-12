"""Yandex Music album tools."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import NotFoundError as FastMCPNotFoundError
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool

from app.controllers.dependencies import get_ym_client
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    ICON_YM,
    TOOL_META,
    ToolCategory,
)
from app.ym.client import YandexMusicClient


@tool(
    title="YM Get Album",
    tags={ToolCategory.YM.value},
    annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    icons=ICON_YM,
    meta=TOOL_META,
)
async def ym_get_album(
    album_id: str,
    include_tracks: bool = False,
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
) -> dict[str, Any]:
    """Get album info from Yandex Music, optionally with tracks.

    Raises :class:`fastmcp.exceptions.NotFoundError` if YM does not
    return an album with the given id (the YM API replies with an empty
    stub or HTTP 400 instead of HTTP 404). Raised as the FastMCP-native
    not-found type so the outer ``ErrorHandlingMiddleware`` maps it to
    MCP error code ``-32001 Not found`` rather than ``-32603``.
    """
    if not album_id or not str(album_id).strip():
        raise ToolError("album_id is required")

    album = await ym.get_album(album_id, with_tracks=include_tracks)

    # YM returns an empty stub (id="" / no title / no artists / 0 tracks)
    # when the album does not exist. Treat as not-found.
    if not album.title and not album.artists and not album.tracks:
        raise FastMCPNotFoundError(f"Album not found: {album_id}")

    return {"album_id": album_id, "album": album.model_dump()}
