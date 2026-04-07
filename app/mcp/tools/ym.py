"""Yandex Music API tools — direct YM access (6 tools, tag: ym).

``ym_playlists`` and ``ym_likes`` dispatch to named handlers via the
shared :class:`ActionDispatcher` (Command registry) instead of
``if/elif`` chains, so adding a new action is a pure addition.
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
    ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    ActionDispatcher,
    ToolCategory,
    UnknownActionError,
)
from app.ym.client import YandexMusicClient

_YM_WRITE_ANNOTATIONS: dict[str, bool] = {"readOnlyHint": False, "openWorldHint": True}
_VALID_SEARCH_TYPES = frozenset({"tracks", "albums", "artists", "playlists", "all"})
_VALID_ARTIST_SORTS = frozenset({"date", "popularity"})
_MAX_BATCH_TRACKS = 100
_MAX_SEARCH_LIMIT = 20
_MAX_LIKED_PAGE = 200


@tool(tags={ToolCategory.YM.value}, annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD)
async def ym_search(
    query: str,
    type: str = "all",
    limit: int = 10,
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search Yandex Music for tracks, albums, artists, playlists.

    ``type`` ∈ ``{tracks, albums, artists, playlists, all}``.
    """
    if type not in _VALID_SEARCH_TYPES:
        raise ToolError(
            f"Invalid type: {type}. Valid: {', '.join(sorted(_VALID_SEARCH_TYPES))}"
        )

    result = await ym.search(query, type=type, limit=min(limit, _MAX_SEARCH_LIMIT))
    return {
        "query": query,
        "type": type,
        "tracks": [t.model_dump() for t in result.tracks],
        "albums": [a.model_dump() for a in result.albums],
        "artists": [a.model_dump() for a in result.artists],
        "playlists": [p.model_dump() for p in result.playlists],
    }


@tool(tags={ToolCategory.YM.value}, annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD)
async def ym_get_tracks(
    track_ids: Any = None,
    fields: str = "id,title,artists,albums,duration_ms",
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Batch get tracks from Yandex Music by IDs (up to 100)."""
    ids = ensure_list(track_ids)
    if not ids:
        raise ToolError("track_ids required")
    if len(ids) > _MAX_BATCH_TRACKS:
        raise ToolError(f"Maximum {_MAX_BATCH_TRACKS} track IDs per request")

    tracks = await ym.get_tracks(ids)
    if fields == "all":
        tracks_data = [t.model_dump() for t in tracks]
    else:
        wanted = {f.strip() for f in fields.split(",")}
        tracks_data = [
            {k: v for k, v in t.model_dump().items() if k in wanted} for t in tracks
        ]
    return {"count": len(tracks_data), "tracks": tracks_data}


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


@tool(tags={ToolCategory.YM.value}, annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD)
async def ym_artist_tracks(
    artist_id: str,
    page: int = 0,
    sort_by: str = "date",
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get paginated tracks by artist from Yandex Music.

    ``sort_by`` ∈ ``{date, popularity}``.
    """
    if sort_by not in _VALID_ARTIST_SORTS:
        raise ToolError(
            f"Invalid sort_by: {sort_by}. Valid: {', '.join(sorted(_VALID_ARTIST_SORTS))}"
        )

    tracks = await ym.get_artist_tracks(artist_id, page=page)
    return {
        "artist_id": artist_id,
        "page": page,
        "sort_by": sort_by,
        "count": len(tracks),
        "tracks": [
            {"id": t.id, "title": t.title, "duration_ms": t.duration_ms, "albums": t.albums}
            for t in tracks
        ],
        "has_next": len(tracks) >= _MAX_SEARCH_LIMIT,
    }


# ── ym_playlists action registry ────────────────────

_playlists_dispatcher: ActionDispatcher[dict[str, Any]] = ActionDispatcher()


@_playlists_dispatcher.register("list")
async def _ym_playlists_list(
    *, ym: YandexMusicClient, **_: Any,
) -> dict[str, Any]:
    playlists = await ym.list_user_playlists()
    return {"action": "list", "playlists": [p.model_dump() for p in playlists]}


@_playlists_dispatcher.register("get")
async def _ym_playlists_get(
    *, kind: int | None, ym: YandexMusicClient, **_: Any,
) -> dict[str, Any]:
    if kind is None:
        raise ToolError("kind required for action 'get'")
    pl = await ym.get_playlist(settings.ym_user_id, kind)
    return {"action": "get", "playlist": pl.model_dump()}


@_playlists_dispatcher.register("get_tracks")
async def _ym_playlists_get_tracks(
    *, kind: int | None, ym: YandexMusicClient, **_: Any,
) -> dict[str, Any]:
    if kind is None:
        raise ToolError("kind required for action 'get_tracks'")
    tracks = await ym.get_playlist_tracks(settings.ym_user_id, kind)
    return {
        "action": "get_tracks",
        "kind": kind,
        "count": len(tracks),
        "track_ids": [t.id for t in tracks],
        "tracks": [
            {
                "id": t.id,
                "title": t.title,
                "artists": [
                    a.get("name", "") if isinstance(a, dict) else a.name
                    for a in (t.artists or [])
                ],
            }
            for t in tracks
        ],
    }


@_playlists_dispatcher.register("create")
async def _ym_playlists_create(
    *, name: str | None, ym: YandexMusicClient, **_: Any,
) -> dict[str, Any]:
    if not name:
        raise ToolError("name required for action 'create'")
    pl = await ym.create_playlist(name)
    return {"action": "create", "playlist": pl.model_dump()}


@_playlists_dispatcher.register("rename")
async def _ym_playlists_rename(
    *, kind: int | None, name: str | None, ym: YandexMusicClient, **_: Any,
) -> dict[str, Any]:
    if kind is None:
        raise ToolError("kind required for action 'rename'")
    if not name:
        raise ToolError("name required for action 'rename'")
    await ym.rename_playlist(kind, name)
    return {"action": "rename", "kind": kind, "new_name": name}


@_playlists_dispatcher.register("delete")
async def _ym_playlists_delete(
    *, kind: int | None, ym: YandexMusicClient, **_: Any,
) -> dict[str, Any]:
    if kind is None:
        raise ToolError("kind required for action 'delete'")
    await ym.delete_playlist(kind)
    return {"action": "delete", "kind": kind}


@_playlists_dispatcher.register("add_tracks")
async def _ym_playlists_add_tracks(
    *,
    kind: int | None,
    track_ids: list[str] | None,
    revision: int | None,
    ym: YandexMusicClient,
    **_: Any,
) -> dict[str, Any]:
    if kind is None:
        raise ToolError("kind required for action 'add_tracks'")
    if not track_ids:
        raise ToolError("track_ids required for action 'add_tracks'")
    if revision is None:
        raise ToolError("revision required for action 'add_tracks'")
    resolved_ids = await ym.resolve_track_ids_with_albums(track_ids)
    result = await ym.add_tracks_to_playlist(kind, resolved_ids, revision)
    return {"action": "add_tracks", "kind": kind, "result": result}


@_playlists_dispatcher.register("remove_tracks")
async def _ym_playlists_remove_tracks(
    *,
    kind: int | None,
    track_ids: list[str] | None,
    revision: int | None,
    ym: YandexMusicClient,
    **_: Any,
) -> dict[str, Any]:
    if kind is None:
        raise ToolError("kind required for action 'remove_tracks'")
    if not track_ids:
        raise ToolError("track_ids required for action 'remove_tracks'")

    pl_tracks = await ym.get_playlist_tracks(settings.ym_user_id, kind)
    rev: int = revision or 0

    id_to_indices: dict[str, list[int]] = {}
    for idx, t in enumerate(pl_tracks):
        if t.id in track_ids:
            id_to_indices.setdefault(t.id, []).append(idx)

    not_found = [tid for tid in track_ids if tid not in id_to_indices]
    indices_to_remove = sorted(
        [idx for indices in id_to_indices.values() for idx in indices],
        reverse=True,
    )

    removed = 0
    for idx in indices_to_remove:
        result_data = await ym.remove_tracks_from_playlist(kind, idx, idx + 1, rev)
        rev = result_data.get("revision", rev + 1)
        removed += 1

    return {
        "action": "remove_tracks",
        "kind": kind,
        "removed": removed,
        "not_found": not_found,
        "revision": rev,
    }


@tool(tags={ToolCategory.YM.value}, annotations=_YM_WRITE_ANNOTATIONS)
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
        return await _playlists_dispatcher.dispatch(
            action,
            kind=kind,
            name=name,
            track_ids=ids,
            revision=revision,
            ym=ym,
        )
    except UnknownActionError as e:
        raise ToolError(str(e)) from e


# ── ym_likes action registry ────────────────────────

_likes_dispatcher: ActionDispatcher[dict[str, Any]] = ActionDispatcher()


@_likes_dispatcher.register("get_liked")
async def _ym_likes_get(
    *, ym: YandexMusicClient, **_: Any,
) -> dict[str, Any]:
    liked = await ym.get_liked_ids()
    return {
        "action": "get_liked",
        "count": len(liked),
        "liked_ids": liked[:_MAX_LIKED_PAGE],
        "truncated": len(liked) > _MAX_LIKED_PAGE,
    }


@_likes_dispatcher.register("add")
async def _ym_likes_add(
    *, track_ids: list[str] | None, ym: YandexMusicClient, **_: Any,
) -> dict[str, Any]:
    if not track_ids:
        raise ToolError("track_ids required for action 'add'")
    await ym.add_likes(track_ids)
    return {"action": "add", "track_ids": track_ids, "success": True}


@_likes_dispatcher.register("remove")
async def _ym_likes_remove(
    *, track_ids: list[str] | None, ym: YandexMusicClient, **_: Any,
) -> dict[str, Any]:
    if not track_ids:
        raise ToolError("track_ids required for action 'remove'")
    await ym.remove_likes(track_ids)
    return {"action": "remove", "track_ids": track_ids, "success": True}


@tool(tags={ToolCategory.YM.value}, annotations=_YM_WRITE_ANNOTATIONS)
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
        return await _likes_dispatcher.dispatch(action, track_ids=ids, ym=ym)
    except UnknownActionError as e:
        raise ToolError(str(e)) from e
