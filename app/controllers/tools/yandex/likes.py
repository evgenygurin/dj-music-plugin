"""Yandex Music likes tools; ``ym_likes`` dispatches list/add/remove via ActionDispatcher."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from pydantic import Field

from app.clients.ym.client import YandexMusicClient
from app.controllers.dependencies import get_ym_client
from app.controllers.tools._shared import (
    ANNOTATIONS_WRITE_OPEN_WORLD,
    ICON_YM,
    TOOL_META,
    ActionDispatcher,
    ToolCategory,
    UnknownActionError,
)
from app.controllers.tools.yandex._constants import MAX_LIKED_PAGE
from app.core.utils.parsing import ensure_list
from app.schemas.ym_responses import YMLikesActionResult

LikesAction = Literal["get_liked", "add", "remove"]

_dispatcher: ActionDispatcher[dict[str, Any]] = ActionDispatcher()


@_dispatcher.register("get_liked")
async def _get_liked(
    *,
    ym: YandexMusicClient,
    limit: int | None = None,
    offset: int = 0,
    **_: Any,
) -> dict[str, Any]:
    liked_set = await ym.get_liked_ids()
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
    ym: YandexMusicClient,
    **_: Any,
) -> dict[str, Any]:
    if not track_ids:
        raise ToolError("track_ids required for action 'add'")
    await ym.add_likes(track_ids)
    return {"action": "add", "track_ids": track_ids, "success": True}


@_dispatcher.register("remove")
async def _remove(
    *,
    track_ids: list[str] | None,
    ym: YandexMusicClient,
    **_: Any,
) -> dict[str, Any]:
    if not track_ids:
        raise ToolError("track_ids required for action 'remove'")
    await ym.remove_likes(track_ids)
    return {"action": "remove", "track_ids": track_ids, "success": True}


@tool(
    title="YM Likes",
    tags={ToolCategory.YM.value},
    annotations=ANNOTATIONS_WRITE_OPEN_WORLD,
    icons=ICON_YM,
    meta=TOOL_META,
)
async def ym_likes(
    action: Annotated[LikesAction, Field(description="Operation to perform")] = "get_liked",
    track_ids: Annotated[
        str | list[str] | None,
        Field(description="YM track ID(s) — required for 'add' and 'remove'"),
    ] = None,
    limit: Annotated[
        int | None,
        Field(description="Page size for get_liked (max 200)", ge=1, le=MAX_LIKED_PAGE),
    ] = None,
    offset: Annotated[int, Field(description="Offset for get_liked pagination", ge=0)] = 0,
    ym: Annotated[
        YandexMusicClient,
        Field(description="Yandex Music API client (injected)."),
        Depends(get_ym_client),
    ] = Depends(get_ym_client),  # noqa: B008
) -> YMLikesActionResult:
    """List, add, or remove liked tracks on the user's Yandex Music account. Use when syncing hearts, curating a liked pool, or undoing likes."""
    ids = ensure_list(track_ids) or None
    try:
        raw = await _dispatcher.dispatch(
            action,
            track_ids=ids,
            ym=ym,
            limit=limit,
            offset=offset,
        )
    except UnknownActionError as e:
        raise ToolError(str(e)) from e
    return YMLikesActionResult(**raw)
