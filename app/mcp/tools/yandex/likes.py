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
    **_: Any,
) -> dict[str, Any]:
    liked = await ym.get_liked_ids()
    return {
        "action": "get_liked",
        "count": len(liked),
        "liked_ids": liked[:MAX_LIKED_PAGE],
        "truncated": len(liked) > MAX_LIKED_PAGE,
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
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Consolidated likes operations on Yandex Music.

    ``action`` ∈ ``{get_liked, add, remove}``.
    """
    ids = ensure_list(track_ids) or None
    try:
        return await _dispatcher.dispatch(action, track_ids=ids, ym=ym)
    except UnknownActionError as e:
        raise ToolError(str(e)) from e
