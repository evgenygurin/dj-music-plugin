"""Yandex Music API tools — direct YM access (6 tools, tag: ym)."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import CurrentContext
from fastmcp.server.context import Context

from app.server import mcp

# ── 1. ym_search ───────────────────────────────────


@mcp.tool(
    tags={"ym"},
    annotations={"readOnlyHint": True, "openWorldHint": True},
)
async def ym_search(
    query: str,
    type: str = "all",
    limit: int = 10,
    ctx: Context = CurrentContext(),
) -> dict[str, Any]:
    """Search Yandex Music for tracks, albums, artists, playlists.

    type: tracks | albums | artists | playlists | all.
    """
    valid_types = ("tracks", "albums", "artists", "playlists", "all")
    if type not in valid_types:
        return {"error": f"Invalid type: {type}. Valid: {', '.join(valid_types)}"}

    # Stub — real implementation needs YM client from lifespan
    return {
        "query": query,
        "type": type,
        "limit": limit,
        "tracks": [],
        "albums": [],
        "artists": [],
        "playlists": [],
        "note": "Stub — configure DJ_YM_TOKEN for real results",
    }


# ── 2. ym_get_tracks ──────────────────────────────


@mcp.tool(
    tags={"ym"},
    annotations={"readOnlyHint": True, "openWorldHint": True},
)
async def ym_get_tracks(
    track_ids: list[str],
    ctx: Context = CurrentContext(),
) -> dict[str, Any]:
    """Batch get tracks from Yandex Music by IDs (up to 100)."""
    if not track_ids:
        return {"error": "track_ids required"}
    if len(track_ids) > 100:
        return {"error": "Maximum 100 track IDs per request"}

    # Stub — real implementation needs YM client from lifespan
    return {
        "track_ids": track_ids,
        "tracks": [],
        "note": "Stub — configure DJ_YM_TOKEN for real results",
    }


# ── 3. ym_get_album ───────────────────────────────


@mcp.tool(
    tags={"ym"},
    annotations={"readOnlyHint": True, "openWorldHint": True},
)
async def ym_get_album(
    album_id: str,
    include_tracks: bool = False,
    ctx: Context = CurrentContext(),
) -> dict[str, Any]:
    """Get album info from Yandex Music, optionally with tracks."""
    # Stub — real implementation needs YM client from lifespan
    return {
        "album_id": album_id,
        "include_tracks": include_tracks,
        "album": None,
        "tracks": [] if include_tracks else None,
        "note": "Stub — configure DJ_YM_TOKEN for real results",
    }


# ── 4. ym_artist_tracks ───────────────────────────


@mcp.tool(
    tags={"ym"},
    annotations={"readOnlyHint": True, "openWorldHint": True},
)
async def ym_artist_tracks(
    artist_id: str,
    page: int = 0,
    sort_by: str = "date",
    ctx: Context = CurrentContext(),
) -> dict[str, Any]:
    """Get paginated tracks by artist from Yandex Music.

    sort_by: date | popularity.
    """
    valid_sorts = ("date", "popularity")
    if sort_by not in valid_sorts:
        return {"error": f"Invalid sort_by: {sort_by}. Valid: {', '.join(valid_sorts)}"}

    # Stub — real implementation needs YM client from lifespan
    return {
        "artist_id": artist_id,
        "page": page,
        "sort_by": sort_by,
        "tracks": [],
        "has_next": False,
        "note": "Stub — configure DJ_YM_TOKEN for real results",
    }


# ── 5. ym_playlists ───────────────────────────────


@mcp.tool(
    tags={"ym"},
    annotations={"openWorldHint": True},
)
async def ym_playlists(
    action: str = "list",
    kind: int | None = None,
    name: str | None = None,
    track_ids: list[str] | None = None,
    revision: int | None = None,
    ctx: Context = CurrentContext(),
) -> dict[str, Any]:
    """Consolidated playlist operations on Yandex Music.

    action: get | list | create | rename | delete | add_tracks | remove_tracks.
    kind: playlist kind (required for get/rename/delete/add_tracks/remove_tracks).
    name: playlist name (required for create/rename).
    track_ids: track IDs (required for add_tracks/remove_tracks).
    revision: playlist revision (required for add_tracks/remove_tracks).
    """
    valid_actions = ("get", "list", "create", "rename", "delete", "add_tracks", "remove_tracks")
    if action not in valid_actions:
        return {"error": f"Invalid action: {action}. Valid: {', '.join(valid_actions)}"}

    if action in ("get", "rename", "delete", "add_tracks", "remove_tracks") and kind is None:
        return {"error": f"kind required for action '{action}'"}

    if action in ("create", "rename") and not name:
        return {"error": f"name required for action '{action}'"}

    if action in ("add_tracks", "remove_tracks"):
        if not track_ids:
            return {"error": f"track_ids required for action '{action}'"}
        if revision is None:
            return {"error": f"revision required for action '{action}'"}

    # Stub — real implementation needs YM client from lifespan
    return {
        "action": action,
        "kind": kind,
        "result": None,
        "note": "Stub — configure DJ_YM_TOKEN for real results",
    }


# ── 6. ym_likes ───────────────────────────────────


@mcp.tool(
    tags={"ym"},
    annotations={"openWorldHint": True},
)
async def ym_likes(
    action: str = "get_liked",
    track_ids: list[str] | None = None,
    ctx: Context = CurrentContext(),
) -> dict[str, Any]:
    """Consolidated likes operations on Yandex Music.

    action: get_liked | add | remove.
    track_ids: required for add/remove.
    """
    valid_actions = ("get_liked", "add", "remove")
    if action not in valid_actions:
        return {"error": f"Invalid action: {action}. Valid: {', '.join(valid_actions)}"}

    if action in ("add", "remove") and not track_ids:
        return {"error": f"track_ids required for action '{action}'"}

    # Stub — real implementation needs YM client from lifespan
    return {
        "action": action,
        "track_ids": track_ids,
        "liked_ids": [] if action == "get_liked" else None,
        "success": None if action == "get_liked" else False,
        "note": "Stub — configure DJ_YM_TOKEN for real results",
    }
