"""Yandex Music API tools — direct YM access (6 tools, tag: ym)."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.mcp.dependencies import get_ym_client
from app.ym.client import YandexMusicClient

# ── 1. ym_search ───────────────────────────────────


@tool(
    tags={"ym"},
    annotations={"readOnlyHint": True, "openWorldHint": True},
)
async def ym_search(
    query: str,
    type: str = "all",
    limit: int = 10,
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search Yandex Music for tracks, albums, artists, playlists.

    type: tracks | albums | artists | playlists | all.
    """
    valid_types = ("tracks", "albums", "artists", "playlists", "all")
    if type not in valid_types:
        raise ToolError(f"Invalid type: {type}. Valid: {', '.join(valid_types)}")

    if limit > 20:
        limit = 20

    result = await ym.search(query, type=type, limit=limit)
    return {
        "query": query,
        "type": type,
        "tracks": [t.model_dump() for t in result.tracks],
        "albums": [a.model_dump() for a in result.albums],
        "artists": [a.model_dump() for a in result.artists],
        "playlists": [p.model_dump() for p in result.playlists],
    }


# ── 2. ym_get_tracks ──────────────────────────────


@tool(
    tags={"ym"},
    annotations={"readOnlyHint": True, "openWorldHint": True},
)
async def ym_get_tracks(
    track_ids: Any = None,
    fields: str = "id,title,artists,albums,duration_ms",
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Batch get tracks from Yandex Music by IDs (up to 100).

    fields: comma-separated fields to return (default: id,title,artists,albums,duration_ms).
    Use "all" for all fields.
    """
    from app.core.parsing import ensure_list

    track_ids = ensure_list(track_ids)
    if not track_ids:
        raise ToolError("track_ids required")
    if len(track_ids) > 100:
        raise ToolError("Maximum 100 track IDs per request")

    tracks = await ym.get_tracks(track_ids)
    if fields == "all":
        tracks_data = [t.model_dump() for t in tracks]
    else:
        wanted = {f.strip() for f in fields.split(",")}
        tracks_data = [{k: v for k, v in t.model_dump().items() if k in wanted} for t in tracks]
    return {
        "count": len(tracks_data),
        "tracks": tracks_data,
    }


# ── 3. ym_get_album ───────────────────────────────


@tool(
    tags={"ym"},
    annotations={"readOnlyHint": True, "openWorldHint": True},
)
async def ym_get_album(
    album_id: str,
    include_tracks: bool = False,
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get album info from Yandex Music, optionally with tracks."""
    album = await ym.get_album(album_id, with_tracks=include_tracks)
    return {
        "album_id": album_id,
        "album": album.model_dump(),
    }


# ── 4. ym_artist_tracks ───────────────────────────


@tool(
    tags={"ym"},
    annotations={"readOnlyHint": True, "openWorldHint": True},
)
async def ym_artist_tracks(
    artist_id: str,
    page: int = 0,
    sort_by: str = "date",
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get paginated tracks by artist from Yandex Music.

    sort_by: date | popularity.
    """
    valid_sorts = ("date", "popularity")
    if sort_by not in valid_sorts:
        raise ToolError(f"Invalid sort_by: {sort_by}. Valid: {', '.join(valid_sorts)}")

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
        "has_next": len(tracks) >= 20,
    }


# ── 5. ym_playlists ───────────────────────────────


@tool(
    tags={"ym"},
    annotations={"readOnlyHint": False, "openWorldHint": True},
)
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

    action: get | get_tracks | list | create | rename | delete | add_tracks | remove_tracks.
    kind: playlist kind (required for get/get_tracks/rename/delete/add_tracks/remove_tracks).
    name: playlist name (required for create/rename).
    track_ids: track IDs (required for add_tracks/remove_tracks).
    revision: playlist revision (required for add_tracks/remove_tracks).
    """
    from app.core.parsing import ensure_list

    track_ids = ensure_list(track_ids) or None
    valid_actions = (
        "get",
        "get_tracks",
        "list",
        "create",
        "rename",
        "delete",
        "add_tracks",
        "remove_tracks",
    )
    if action not in valid_actions:
        raise ToolError(f"Invalid action: {action}. Valid: {', '.join(valid_actions)}")

    if (
        action in ("get", "get_tracks", "rename", "delete", "add_tracks", "remove_tracks")
        and kind is None
    ):
        raise ToolError(f"kind required for action '{action}'")

    if action in ("create", "rename") and not name:
        raise ToolError(f"name required for action '{action}'")

    if action in ("add_tracks", "remove_tracks"):
        if not track_ids:
            raise ToolError(f"track_ids required for action '{action}'")
        if revision is None:
            raise ToolError(f"revision required for action '{action}'")

    from app.config import settings

    if action == "list":
        playlists = await ym.list_user_playlists()
        return {"action": "list", "playlists": [p.model_dump() for p in playlists]}

    if action == "get":
        pl = await ym.get_playlist(settings.ym_user_id, kind)  # type: ignore[arg-type]
        return {"action": "get", "playlist": pl.model_dump()}

    if action == "get_tracks":
        tracks = await ym.get_playlist_tracks(settings.ym_user_id, kind)  # type: ignore[arg-type]
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

    if action == "create":
        pl = await ym.create_playlist(name)  # type: ignore[arg-type]
        return {"action": "create", "playlist": pl.model_dump()}

    if action == "rename":
        await ym.rename_playlist(kind, name)  # type: ignore[arg-type]
        return {"action": "rename", "kind": kind, "new_name": name}

    if action == "delete":
        await ym.delete_playlist(kind)  # type: ignore[arg-type]
        return {"action": "delete", "kind": kind}

    if action == "add_tracks":
        # Auto-resolve bare track IDs to "trackId:albumId" format required by YM API
        resolved_ids = await ym.resolve_track_ids_with_albums(track_ids)  # type: ignore[arg-type]
        result = await ym.add_tracks_to_playlist(
            kind,
            resolved_ids,
            revision,  # type: ignore[arg-type]
        )
        return {"action": "add_tracks", "kind": kind, "result": result}

    if action == "remove_tracks":
        # YM API removes by index range, not track IDs.
        # Look up current playlist to find indices of given track_ids, then remove.
        pl = await ym.get_playlist(settings.ym_user_id, kind)  # type: ignore[arg-type]
        pl_tracks = await ym.get_playlist_tracks(settings.ym_user_id, kind)  # type: ignore[arg-type]
        rev = revision  # type: ignore[assignment]

        # Build track_id → index mapping
        id_to_indices: dict[str, list[int]] = {}
        for idx, t in enumerate(pl_tracks):
            if t.id in track_ids:
                id_to_indices.setdefault(t.id, []).append(idx)

        not_found = [tid for tid in track_ids if tid not in id_to_indices]

        # Collect all indices to remove, sort descending to avoid index shift
        indices_to_remove = sorted(
            [idx for indices in id_to_indices.values() for idx in indices],
            reverse=True,
        )

        removed = 0
        for idx in indices_to_remove:
            result_data = await ym.remove_tracks_from_playlist(kind, idx, idx + 1, rev)  # type: ignore[arg-type]
            rev = result_data.get("revision", rev + 1)
            removed += 1

        return {
            "action": "remove_tracks",
            "kind": kind,
            "removed": removed,
            "not_found": not_found,
            "revision": rev,
        }

    raise ToolError("Unreachable")


# ── 6. ym_likes ───────────────────────────────────


@tool(
    tags={"ym"},
    annotations={"readOnlyHint": False, "openWorldHint": True},
)
async def ym_likes(
    action: str = "get_liked",
    track_ids: Any = None,
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Consolidated likes operations on Yandex Music.

    action: get_liked | add | remove.
    track_ids: required for add/remove.
    """
    from app.core.parsing import ensure_list

    track_ids = ensure_list(track_ids) or None
    valid_actions = ("get_liked", "add", "remove")
    if action not in valid_actions:
        raise ToolError(f"Invalid action: {action}. Valid: {', '.join(valid_actions)}")

    if action in ("add", "remove") and not track_ids:
        raise ToolError(f"track_ids required for action '{action}'")

    if action == "get_liked":
        liked = await ym.get_liked_ids()
        return {
            "action": "get_liked",
            "count": len(liked),
            "liked_ids": liked[:200],
            "truncated": len(liked) > 200,
        }

    if action == "add":
        await ym.add_likes(track_ids)
        return {"action": "add", "track_ids": track_ids, "success": True}

    if action == "remove":
        await ym.remove_likes(track_ids)
        return {"action": "remove", "track_ids": track_ids, "success": True}

    raise ToolError("Unreachable")
