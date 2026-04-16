"""Platform playlist tools; ``platform_playlists`` dispatches CRUD/track actions."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from pydantic import Field, TypeAdapter

from app.controllers.dependencies.external import get_music_provider
from app.controllers.tools._shared import (
    ANNOTATIONS_WRITE_OPEN_WORLD,
    ICON_YM,
    TOOL_META,
    ActionDispatcher,
    ToolCategory,
    UnknownActionError,
)
from app.controllers.tools.platform._constants import MAX_PLAYLIST_TRACKS_PAGE
from app.core.utils.parsing import ensure_list
from app.providers.protocol import MusicProvider
from app.schemas.platform_responses import PlaylistActionResult

PlaylistAction = Literal[
    "list",
    "get",
    "get_tracks",
    "create",
    "rename",
    "delete",
    "add_tracks",
    "remove_tracks",
    "update",
]

_dispatcher: ActionDispatcher[dict[str, Any]] = ActionDispatcher()
DEFAULT_PLAYLISTS_PAGE = 50
_playlist_action_result_adapter: TypeAdapter[PlaylistActionResult] = TypeAdapter(
    PlaylistActionResult
)


def _require_playlist_id(playlist_id: str | None, action: str) -> str:
    if not playlist_id:
        raise ToolError(f"playlist_id required for action {action!r}")
    return playlist_id


def _require_name(name: str | None, action: str) -> str:
    if not name:
        raise ToolError(f"name required for action {action!r}")
    return name


def _require_track_ids(track_ids: list[str] | None, action: str) -> list[str]:
    if not track_ids:
        raise ToolError(f"track_ids required for action {action!r}")
    return track_ids


async def _validate_track_ids_exist(provider: MusicProvider, track_ids: list[str]) -> None:
    """Fail fast when requested platform IDs are not resolvable."""
    try:
        tracks = await provider.get_tracks(track_ids)
    except Exception as exc:  # pragma: no cover - provider-specific transport errors
        raise ToolError(
            "Could not validate platform track_ids. Check IDs with get_platform_tracks first."
        ) from exc
    returned_ids = {track.id for track in tracks}
    missing = [track_id for track_id in track_ids if track_id not in returned_ids]
    if missing:
        sample = ", ".join(missing[:10])
        raise ToolError(f"Unknown platform track_ids: {sample}")


@_dispatcher.register("list")
async def _list(
    *,
    provider: MusicProvider,
    limit: int | None = None,
    offset: int = 0,
    **_: Any,
) -> dict[str, Any]:
    if offset < 0:
        raise ToolError(f"offset must be >= 0, got {offset}")
    page_size = (
        DEFAULT_PLAYLISTS_PAGE if limit is None else min(max(limit, 1), MAX_PLAYLIST_TRACKS_PAGE)
    )
    playlists = await provider.list_user_playlists()
    total = len(playlists)
    page = playlists[offset : offset + page_size]
    next_offset = offset + len(page)
    return {
        "action": "list",
        "playlists": [p.model_dump(mode="json") for p in page],
        "count": total,
        "offset": offset,
        "limit": page_size,
        "next_offset": next_offset if next_offset < total else None,
        "truncated": next_offset < total,
    }


@_dispatcher.register("get")
async def _get(
    *,
    playlist_id: str | None,
    provider: MusicProvider,
    **_: Any,
) -> dict[str, Any]:
    resolved_playlist_id = _require_playlist_id(playlist_id, "get")
    pl = await provider.get_playlist(resolved_playlist_id)
    return {"action": "get", "playlist_id": resolved_playlist_id, "playlist": pl.model_dump()}


@_dispatcher.register("get_tracks")
async def _get_tracks(
    *,
    playlist_id: str | None,
    provider: MusicProvider,
    limit: int | None = None,
    offset: int = 0,
    **_: Any,
) -> dict[str, Any]:
    resolved_playlist_id = _require_playlist_id(playlist_id, "get_tracks")
    if offset < 0:
        raise ToolError(f"offset must be >= 0, got {offset}")
    page_size = (
        MAX_PLAYLIST_TRACKS_PAGE if limit is None else min(max(limit, 1), MAX_PLAYLIST_TRACKS_PAGE)
    )

    tracks = await provider.get_playlist_tracks(resolved_playlist_id)
    total = len(tracks)
    page = tracks[offset : offset + page_size]
    next_offset = offset + len(page)

    return {
        "action": "get_tracks",
        "playlist_id": resolved_playlist_id,
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
    title: str | None,
    provider: MusicProvider,
    **_: Any,
) -> dict[str, Any]:
    resolved_name = name or title
    pl = await provider.create_playlist(_require_name(resolved_name, "create"))
    return {"action": "create", "playlist": pl.model_dump()}


@_dispatcher.register("rename")
async def _rename(
    *,
    playlist_id: str | None,
    name: str | None,
    provider: MusicProvider,
    **_: Any,
) -> dict[str, Any]:
    resolved_playlist_id = _require_playlist_id(playlist_id, "rename")
    resolved_name = _require_name(name, "rename")
    await provider.rename_playlist(resolved_playlist_id, resolved_name)
    return {"action": "rename", "playlist_id": resolved_playlist_id, "new_name": resolved_name}


@_dispatcher.register("delete")
async def _delete(
    *,
    playlist_id: str | None,
    provider: MusicProvider,
    **_: Any,
) -> dict[str, Any]:
    resolved_playlist_id = _require_playlist_id(playlist_id, "delete")
    await provider.delete_playlist(resolved_playlist_id)
    return {"action": "delete", "playlist_id": resolved_playlist_id}


@_dispatcher.register("add_tracks")
async def _add_tracks(
    *,
    playlist_id: str | None,
    track_ids: list[str] | None,
    provider: MusicProvider,
    **_: Any,
) -> dict[str, Any]:
    resolved_playlist_id = _require_playlist_id(playlist_id, "add_tracks")
    resolved_ids = _require_track_ids(track_ids, "add_tracks")
    try:
        await _validate_track_ids_exist(provider, resolved_ids)
        await provider.add_tracks_to_playlist(resolved_playlist_id, resolved_ids)
    except ToolError as exc:
        return {
            "action": "add_tracks",
            "playlist_id": resolved_playlist_id,
            "result": {
                "ok": False,
                "added": 0,
                "removed": 0,
                "changed_count": 0,
                "error": str(exc),
            },
        }
    n = len(resolved_ids)
    return {
        "action": "add_tracks",
        "playlist_id": resolved_playlist_id,
        "result": {
            "ok": True,
            "added": n,
            "removed": 0,
            "changed_count": n,
        },
    }


@_dispatcher.register("remove_tracks")
async def _remove_tracks(
    *,
    playlist_id: str | None,
    track_ids: list[str] | None,
    provider: MusicProvider,
    **_: Any,
) -> dict[str, Any]:
    resolved_playlist_id = _require_playlist_id(playlist_id, "remove_tracks")
    resolved_ids = _require_track_ids(track_ids, "remove_tracks")
    try:
        await _validate_track_ids_exist(provider, resolved_ids)
    except ToolError as exc:
        return {
            "action": "remove_tracks",
            "playlist_id": resolved_playlist_id,
            "removed": 0,
            "result": {
                "ok": False,
                "added": 0,
                "removed": 0,
                "changed_count": 0,
                "error": str(exc),
            },
        }
    before_tracks = await provider.get_playlist_tracks(resolved_playlist_id)
    before_ids = [track.id for track in before_tracks]
    await provider.remove_tracks_from_playlist(resolved_playlist_id, resolved_ids)
    after_tracks = await provider.get_playlist_tracks(resolved_playlist_id)
    after_ids = {track.id for track in after_tracks}
    removed_count = sum(1 for track_id in before_ids if track_id not in after_ids)
    return {
        "action": "remove_tracks",
        "playlist_id": resolved_playlist_id,
        "removed": removed_count,
        "result": {
            "ok": True,
            "added": 0,
            "removed": removed_count,
            "changed_count": removed_count,
        },
    }


@_dispatcher.register("update")
async def _update(
    *,
    playlist_id: str | None,
    track_ids: list[str] | None,
    provider: MusicProvider,
    **_: Any,
) -> dict[str, Any]:
    """Replace playlist tracks in one action for MCP clients."""
    resolved_playlist_id = _require_playlist_id(playlist_id, "update")
    if track_ids is None:
        raise ToolError("track_ids required for action 'update'")
    if track_ids:
        try:
            await _validate_track_ids_exist(provider, track_ids)
        except ToolError as exc:
            return {
                "action": "update",
                "playlist_id": resolved_playlist_id,
                "removed": 0,
                "added": 0,
                "result": {
                    "ok": False,
                    "added": 0,
                    "removed": 0,
                    "changed_count": 0,
                    "error": str(exc),
                },
            }

    existing_tracks = await provider.get_playlist_tracks(resolved_playlist_id)
    existing_ids = [track.id for track in existing_tracks]
    if existing_ids:
        await provider.remove_tracks_from_playlist(resolved_playlist_id, existing_ids)
    if track_ids:
        await provider.add_tracks_to_playlist(resolved_playlist_id, track_ids)

    n_removed = len(existing_ids)
    n_added = len(track_ids)
    return {
        "action": "update",
        "playlist_id": resolved_playlist_id,
        "removed": n_removed,
        "added": n_added,
        "result": {
            "ok": True,
            "removed": n_removed,
            "added": n_added,
            "changed_count": n_removed + n_added,
        },
    }


@tool(
    title="Platform Playlists",
    tags={ToolCategory.PLATFORM.value},
    annotations=ANNOTATIONS_WRITE_OPEN_WORLD,
    icons=ICON_YM,
    meta=TOOL_META,
)
async def platform_playlists(
    action: Annotated[PlaylistAction, Field(description="Operation to perform")] = "list",
    playlist_id: Annotated[
        str | None,
        Field(
            description="Platform playlist ID; required for get/get_tracks/rename/delete/add_tracks/remove_tracks"
        ),
    ] = None,
    name: Annotated[
        str | None, Field(description="Playlist name — required for create/rename")
    ] = None,
    title: Annotated[
        str | None,
        Field(description="Alias for name in create/rename (backward-compatible)"),
    ] = None,
    track_ids: Annotated[
        str | list[str] | None,
        Field(description="Platform track ID(s) — required for add_tracks/remove_tracks/update"),
    ] = None,
    revision: Annotated[
        int | None,
        Field(description="Ignored — revision is managed automatically by the provider adapter"),
    ] = None,
    limit: Annotated[
        int | None,
        Field(
            description="Page size for list/get_tracks (max 200)",
            ge=1,
            le=MAX_PLAYLIST_TRACKS_PAGE,
        ),
    ] = None,
    offset: Annotated[int, Field(description="Offset for get_tracks pagination", ge=0)] = 0,
    page: Annotated[
        int | None,
        Field(
            description="Optional page number alias for clients that send page instead of offset"
        ),
    ] = None,
    platform: Annotated[
        str | None,
        Field(description="Ignored. Platform is selected by active provider session."),
    ] = None,
    provider: MusicProvider = Depends(get_music_provider),  # noqa: B008
) -> PlaylistActionResult:
    """List and mutate user playlists on the active music platform."""
    del revision  # revision is now managed internally by the provider adapter
    del page  # compatibility alias; offset remains canonical
    del platform  # provider is resolved via dependency
    ids = None if track_ids is None else ensure_list(track_ids)
    try:
        raw = await _dispatcher.dispatch(
            action,
            playlist_id=playlist_id,
            name=name,
            title=title,
            track_ids=ids,
            limit=limit,
            offset=offset,
            provider=provider,
        )
    except UnknownActionError as e:
        raise ToolError(str(e)) from e
    return _playlist_action_result_adapter.validate_python(raw)
