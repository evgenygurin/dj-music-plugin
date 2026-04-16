"""Platform liked-tracks tool; ``platform_liked_tracks`` dispatches list/add/remove."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from pydantic import Field

from app.controllers.dependencies import get_music_provider
from app.controllers.tools._shared import (
    ANNOTATIONS_WRITE_OPEN_WORLD,
    ICON_YM,
    TOOL_META,
    ActionDispatcher,
    ToolCategory,
    UnknownActionError,
)
from app.controllers.tools.platform._constants import MAX_LIKED_PAGE
from app.core.utils.parsing import ensure_list
from app.providers.protocol import MusicProvider
from app.schemas.platform_responses import LikesActionResult

LikesAction = Literal["get_liked", "add", "remove"]

_dispatcher: ActionDispatcher[dict[str, Any]] = ActionDispatcher()


@_dispatcher.register("get_liked")
async def _get_liked(
    *,
    provider: MusicProvider,
    limit: int | None = None,
    offset: int = 0,
    **_: Any,
) -> dict[str, Any]:
    liked_set = await provider.get_liked_ids()
    liked = sorted(liked_set)
    total = len(liked)

    if offset < 0:
        raise ToolError(f"offset must be >= 0, got {offset}")
    page_size = MAX_LIKED_PAGE if limit is None else min(max(limit, 1), MAX_LIKED_PAGE)

    page = liked[offset : offset + page_size]
    next_offset = offset + len(page)
    return {
        "action": "get_liked",
        "count": total,
        "offset": offset,
        "limit": page_size,
        "liked_ids": page,
        "next_offset": next_offset if next_offset < total else None,
        "truncated": next_offset < total,
    }


@_dispatcher.register("add")
async def _add(
    *,
    track_ids: list[str] | None,
    provider: MusicProvider,
    **_: Any,
) -> dict[str, Any]:
    if not track_ids:
        raise ToolError("track_ids required for action 'add'")
    await provider.add_likes(track_ids)
    return {"action": "add", "track_ids": track_ids, "success": True}


@_dispatcher.register("remove")
async def _remove(
    *,
    track_ids: list[str] | None,
    provider: MusicProvider,
    **_: Any,
) -> dict[str, Any]:
    if not track_ids:
        raise ToolError("track_ids required for action 'remove'")
    await provider.remove_likes(track_ids)
    return {"action": "remove", "track_ids": track_ids, "success": True}


@tool(
    title="Platform Liked Tracks",
    tags={ToolCategory.PLATFORM.value},
    annotations=ANNOTATIONS_WRITE_OPEN_WORLD,
    icons=ICON_YM,
    meta=TOOL_META,
)
async def platform_liked_tracks(
    action: Annotated[LikesAction, Field(description="Operation to perform")] = "get_liked",
    track_ids: Annotated[
        str | list[str] | None,
        Field(description="Platform track ID(s) — required for 'add' and 'remove'"),
    ] = None,
    limit: Annotated[
        int | None,
        Field(description="Page size for get_liked (max 200)", ge=1, le=MAX_LIKED_PAGE),
    ] = None,
    offset: Annotated[int, Field(description="Offset for get_liked pagination", ge=0)] = 0,
    provider: MusicProvider = Depends(get_music_provider),  # noqa: B008
) -> LikesActionResult:
    """List, add, or remove liked tracks on the active music platform."""
    ids = ensure_list(track_ids) or None
    try:
        raw = await _dispatcher.dispatch(
            action,
            track_ids=ids,
            provider=provider,
            limit=limit,
            offset=offset,
        )
    except UnknownActionError as e:
        raise ToolError(str(e)) from e
    return LikesActionResult(**raw)
