"""Yandex Music playlist operations.

Action-parameterised tool ``ym_playlists`` dispatches to named handlers
via :class:`~app.mcp.tools._shared.ActionDispatcher` (Command + Registry
pattern). Adding a new action is a pure addition — no ``if/elif`` edit
required, and duplicate registrations fail loudly at import time.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.config import settings
from app.core.parsing import ensure_list
from app.mcp.dependencies import get_ym_client
from app.mcp.tools._shared import (
    ActionDispatcher,
    ToolCategory,
    UnknownActionError,
)
from app.mcp.tools.yandex._constants import YM_WRITE_ANNOTATIONS
from app.ym.client import YandexMusicClient

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


@_dispatcher.register("list")
async def _list(
    *,
    ym: YandexMusicClient,
    **_: Any,
) -> dict[str, Any]:
    playlists = await ym.list_user_playlists()
    return {"action": "list", "playlists": [p.model_dump() for p in playlists]}


@_dispatcher.register("get")
async def _get(
    *,
    kind: int | None,
    ym: YandexMusicClient,
    **_: Any,
) -> dict[str, Any]:
    pl = await ym.get_playlist(settings.ym_user_id, _require_kind(kind, "get"))
    return {"action": "get", "playlist": pl.model_dump()}


@_dispatcher.register("get_tracks")
async def _get_tracks(
    *,
    kind: int | None,
    ym: YandexMusicClient,
    **_: Any,
) -> dict[str, Any]:
    resolved_kind = _require_kind(kind, "get_tracks")
    tracks = await ym.get_playlist_tracks(settings.ym_user_id, resolved_kind)
    return {
        "action": "get_tracks",
        "kind": resolved_kind,
        "count": len(tracks),
        "track_ids": [t.id for t in tracks],
        "tracks": [
            {
                "id": t.id,
                "title": t.title,
                "artists": [
                    a.get("name", "") if isinstance(a, dict) else a.name for a in (t.artists or [])
                ],
            }
            for t in tracks
        ],
    }


@_dispatcher.register("create")
async def _create(
    *,
    name: str | None,
    ym: YandexMusicClient,
    **_: Any,
) -> dict[str, Any]:
    pl = await ym.create_playlist(_require_name(name, "create"))
    return {"action": "create", "playlist": pl.model_dump()}


@_dispatcher.register("rename")
async def _rename(
    *,
    kind: int | None,
    name: str | None,
    ym: YandexMusicClient,
    **_: Any,
) -> dict[str, Any]:
    resolved_kind = _require_kind(kind, "rename")
    resolved_name = _require_name(name, "rename")
    await ym.rename_playlist(resolved_kind, resolved_name)
    return {"action": "rename", "kind": resolved_kind, "new_name": resolved_name}


@_dispatcher.register("delete")
async def _delete(
    *,
    kind: int | None,
    ym: YandexMusicClient,
    **_: Any,
) -> dict[str, Any]:
    resolved_kind = _require_kind(kind, "delete")
    await ym.delete_playlist(resolved_kind)
    return {"action": "delete", "kind": resolved_kind}


@_dispatcher.register("add_tracks")
async def _add_tracks(
    *,
    kind: int | None,
    track_ids: list[str] | None,
    revision: int | None,
    ym: YandexMusicClient,
    **_: Any,
) -> dict[str, Any]:
    resolved_kind = _require_kind(kind, "add_tracks")
    resolved_ids = _require_track_ids(track_ids, "add_tracks")
    if revision is None:
        raise ToolError("revision required for action 'add_tracks'")
    resolved_with_albums = await ym.resolve_track_ids_with_albums(resolved_ids)
    result = await ym.add_tracks_to_playlist(resolved_kind, resolved_with_albums, revision)
    return {"action": "add_tracks", "kind": resolved_kind, "result": result}


@_dispatcher.register("remove_tracks")
async def _remove_tracks(
    *,
    kind: int | None,
    track_ids: list[str] | None,
    revision: int | None,
    ym: YandexMusicClient,
    **_: Any,
) -> dict[str, Any]:
    resolved_kind = _require_kind(kind, "remove_tracks")
    resolved_ids = _require_track_ids(track_ids, "remove_tracks")

    pl_tracks = await ym.get_playlist_tracks(settings.ym_user_id, resolved_kind)
    rev: int = revision or 0

    id_to_indices: dict[str, list[int]] = {}
    for idx, t in enumerate(pl_tracks):
        if t.id in resolved_ids:
            id_to_indices.setdefault(t.id, []).append(idx)

    not_found = [tid for tid in resolved_ids if tid not in id_to_indices]
    indices_to_remove = sorted(
        [idx for indices in id_to_indices.values() for idx in indices],
        reverse=True,
    )

    removed = 0
    for idx in indices_to_remove:
        result_data = await ym.remove_tracks_from_playlist(resolved_kind, idx, idx + 1, rev)
        rev = result_data.get("revision", rev + 1)
        removed += 1

    return {
        "action": "remove_tracks",
        "kind": resolved_kind,
        "removed": removed,
        "not_found": not_found,
        "revision": rev,
    }


@tool(tags={ToolCategory.YM.value}, annotations=YM_WRITE_ANNOTATIONS)
async def ym_playlists(
    action: str = "list",
    kind: int | None = None,
    name: str | None = None,
    track_ids: Any = None,
    revision: int | None = None,
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Consolidated playlist operations on Yandex Music.

    ``action`` ∈ ``{get, get_tracks, list, create, rename, delete,
    add_tracks, remove_tracks}``.
    """
    ids = ensure_list(track_ids) or None
    try:
        return await _dispatcher.dispatch(
            action,
            kind=kind,
            name=name,
            track_ids=ids,
            revision=revision,
            ym=ym,
        )
    except UnknownActionError as e:
        raise ToolError(str(e)) from e
