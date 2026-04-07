"""Yandex Music album tools."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.mcp.dependencies import get_ym_client
from app.mcp.tools._shared import ANNOTATIONS_READ_ONLY_OPEN_WORLD, ToolCategory
from app.ym.client import YandexMusicClient


@tool(tags={ToolCategory.YM.value}, annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD)
async def ym_get_album(
    album_id: str,
    include_tracks: bool = False,
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get album info from Yandex Music, optionally with tracks."""
    album = await ym.get_album(album_id, with_tracks=include_tracks)
    return {"album_id": album_id, "album": album.model_dump()}
