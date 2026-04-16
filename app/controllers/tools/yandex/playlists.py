"""Yandex Music playlist tools; ``ym_playlists`` dispatches CRUD/track actions via ActionDispatcher."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from pydantic import Field

from app.config import settings
from app.controllers.dependencies.external import get_music_provider
from app.controllers.tools._shared import (
    ANNOTATIONS_WRITE_OPEN_WORLD,
    ICON_YM,
    TOOL_META,
    ActionDispatcher,
    ToolCategory,
    UnknownActionError,
)
from app.controllers.tools.yandex._constants import MAX_PLAYLIST_TRACKS_PAGE
from app.core.utils.parsing import ensure_list
from app.providers.protocol import MusicProvider
from app.schemas.ym_responses import YMPlaylistActionResult

PlaylistAction = Literal[
    "list", "get", "get_tracks", "create", "rename", "delete", "add_tracks", "remove_tracks"
]

_dispatcher: ActionDispatcher[dict[str, Any]] = ActionDispatcher()


def _require_kind(kind: int | None, action: str) -> int:
    if kind is None:
        raise ToolError(f"kind required for action {action!r}")
    return kind


def _require_name(name: str | None, action: str) -> str:
    if not name:
        raise ToolError(f"name required for action {action!r}")
    return name


def _require_track_ids(track_ids: list[str] | None, action: str) -> list[str]:
    if not track_ids:
        raise ToolError(f"track_ids required for action {action!r}")
    return track_ids


def _playlist_id(kind: int) -> str:
    """Format YM playlist ID as ``owner_id:kind`` for the provider adapter."""
    return f"{settings.ym_user_id}:{kind}"


@_dispatcher.register("list")
async def _list(
    *,
    provider: MusicProvider,
    **_: Any,
) -> dict[str, Any]:
    playlists = await provider.list_user_playlists()
    return {"action": "list", "playlists": [p.model_dump() for p in playlists]}


@_dispatcher.register("get")
async def _get(
    *,
    kind: int | None,
    provider: MusicProvider,
    **_: Any,
) -> dict[str, Any]:
    pl = await provider.get_playlist(_playlist_id(_require_kind(kind, "get")))
    return {"action": "get", "playlist": pl.model_dump()}


@_dispatcher.register("get_tracks")
async def _get_tracks(
    *,
    kind: int | None,
    provider: MusicProvider,
    limit: int | None = None,
    offset: int = 0,
    **_: Any,
) -> dict[str, Any]:
    resolved_kind = _require_kind(kind, "get_tracks")
    if offset < 0:
        raise ToolError(f"offset must be >= 0, got {offset}")
    page_size = (
        MAX_PLAYLIST_TRACKS_PAGE if limit is None else min(max(limit, 1), MAX_PLAYLIST_TRACKS_PAGE)
    )

    tracks = await provider.get_playlist_tracks(_playlist_id(resolved_kind))
    total = len(tracks)
    page = tracks[offset : offset + page_size]
    next_offset = offset + len(page)

    return {
        "action": "get_tracks",
        "kind": resolved_kind,
        "count": total,
        "offset": offset,
        "limit": page_size,
        "track_ids": [t.id for t in page],
        "tracks": [
            {
                "id": t.id,
                "title": t.title,
                "artists": [a.name for a in t.artists],
            }
            for t in page
        ],
        "next_offset": next_offset if next_offset < total else None,
        "truncated": next_offset < total,
    }


@_dispatcher.register("create")
async def _create(
    *,
    name: str | None,
    provider: MusicProvider,
    **_: Any,
) -> dict[str, Any]:
    pl = await provider.create_playlist(_require_name(name, "create"))
    return {"action": "create", "playlist": pl.model_dump()}


@_dispatcher.register("rename")
async def _rename(
    *,
    kind: int | None,
    name: str | None,
    provider: MusicProvider,
    **_: Any,
) -> dict[str, Any]:
    resolved_kind = _require_kind(kind, "rename")
    resolved_name = _require_name(name, "rename")
    await provider.rename_playlist(_playlist_id(resolved_kind), resolved_name)
    return {"action": "rename", "kind": resolved_kind, "new_name": resolved_name}


@_dispatcher.register("delete")
async def _delete(
    *,
    kind: int | None,
    provider: MusicProvider,
    **_: Any,
) -> dict[str, Any]:
    resolved_kind = _require_kind(kind, "delete")
    await provider.delete_playlist(_playlist_id(resolved_kind))
    return {"action": "delete", "kind": resolved_kind}


@_dispatcher.register("add_tracks")
async def _add_tracks(
    *,
    kind: int | None,
    track_ids: list[str] | None,
    provider: MusicProvider,
    **_: Any,
) -> dict[str, Any]:
    resolved_kind = _require_kind(kind, "add_tracks")
    resolved_ids = _require_track_ids(track_ids, "add_tracks")
    # Revision is managed internally by the provider adapter.
    await provider.add_tracks_to_playlist(_playlist_id(resolved_kind), resolved_ids)
    return {"action": "add_tracks", "kind": resolved_kind, "result": True}


@_dispatcher.register("remove_tracks")
async def _remove_tracks(
    *,
    kind: int | None,
    track_ids: list[str] | None,
    provider: MusicProvider,
    **_: Any,
) -> dict[str, Any]:
    resolved_kind = _require_kind(kind, "remove_tracks")
    resolved_ids = _require_track_ids(track_ids, "remove_tracks")
    await provider.remove_tracks_from_playlist(_playlist_id(resolved_kind), resolved_ids)
    return {"action": "remove_tracks", "kind": resolved_kind, "removed": len(resolved_ids)}


@tool(
    title="YM Playlists",
    tags={ToolCategory.YM.value},
    annotations=ANNOTATIONS_WRITE_OPEN_WORLD,
    icons=ICON_YM,
    meta=TOOL_META,
)
async def ym_playlists(
    action: Annotated[PlaylistAction, Field(description="Operation to perform")] = "list",
    kind: Annotated[
        int | None,
        Field(
            description="YM playlist number (from list action); required for get/get_tracks/rename/delete/add_tracks/remove_tracks"
        ),
    ] = None,
    name: Annotated[
        str | None, Field(description="Playlist name — required for create/rename")
    ] = None,
    track_ids: Annotated[
        str | list[str] | None,
        Field(description="YM track ID(s) — required for add_tracks/remove_tracks"),
    ] = None,
    revision: Annotated[
        int | None,
        Field(description="Ignored — revision is managed automatically by the provider adapter"),
    ] = None,
    limit: Annotated[
        int | None,
        Field(description="Page size for get_tracks (max 200)", ge=1, le=MAX_PLAYLIST_TRACKS_PAGE),
    ] = None,
    offset: Annotated[int, Field(description="Offset for get_tracks pagination", ge=0)] = 0,
    provider: MusicProvider = Depends(get_music_provider),  # noqa: B008
) -> YMPlaylistActionResult:
    """List and mutate user playlists on Yandex Music (tracks, revisions, kinds). Use when exporting to YM, renaming playlists, or paging playlist tracks."""
    del revision  # revision is now managed internally by the provider adapter
    ids = ensure_list(track_ids) or None
    try:
        raw = await _dispatcher.dispatch(
            action,
            kind=kind,
            name=name,
            track_ids=ids,
            limit=limit,
            offset=offset,
            provider=provider,
        )
    except UnknownActionError as e:
        raise ToolError(str(e)) from e
    return YMPlaylistActionResult(**raw)
