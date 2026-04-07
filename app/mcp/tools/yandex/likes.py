"""Yandex Music likes operations.

Action-parameterised tool ``ym_likes`` dispatches to named handlers via
:class:`~app.mcp.tools._shared.ActionDispatcher`.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.core.parsing import ensure_list
from app.mcp.dependencies import get_ym_client
from app.mcp.tools._shared import (
    ActionDispatcher,
    ToolCategory,
    UnknownActionError,
)
from app.mcp.tools.yandex._constants import MAX_LIKED_PAGE, YM_WRITE_ANNOTATIONS
from app.ym.client import YandexMusicClient

_dispatcher: ActionDispatcher[dict[str, Any]] = ActionDispatcher()


@_dispatcher.register("get_liked")
async def _get_liked(
    *,
    ym: YandexMusicClient,
    limit: int | None = None,
    offset: int = 0,
    **_: Any,
) -> dict[str, Any]:
    liked = await ym.get_liked_ids()
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


@tool(tags={ToolCategory.YM.value}, annotations=YM_WRITE_ANNOTATIONS)
async def ym_likes(
    action: str = "get_liked",
    track_ids: Any = None,
    limit: int | None = None,
    offset: int = 0,
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Consolidated likes operations on Yandex Music.

    ``action`` ∈ ``{get_liked, add, remove}``. ``limit``/``offset`` apply
    only to ``get_liked`` and page through the full liked list (default
    page size is :data:`MAX_LIKED_PAGE`).
    """
    ids = ensure_list(track_ids) or None
    try:
        return await _dispatcher.dispatch(
            action,
            track_ids=ids,
            ym=ym,
            limit=limit,
            offset=offset,
        )
    except UnknownActionError as e:
        raise ToolError(str(e)) from e
