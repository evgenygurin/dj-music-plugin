"""Playlist tools — list, get, manage (3 tools, tag: core).

Thin wrappers calling :class:`PlaylistService` via ``Depends()``.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entity_resolver import resolve_track_refs
from app.core.parsing import ensure_dict, ensure_list
from app.core.schemas import PaginatedResponse, PlaylistSummary
from app.mcp.dependencies import (
    get_db_session,
    get_playlist_service,
    get_track_service,
)
from app.mcp.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE,
    ToolCategory,
    map_domain_errors,
    resolve_entity,
)
from app.services.playlist_service import PlaylistService
from app.services.track_service import TrackService

_PLAYLIST_ACTIONS = frozenset(
    {"create", "update", "delete", "add_tracks", "remove_tracks", "reorder"}
)


@tool(tags={ToolCategory.CORE.value}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def list_playlists(
    source: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    svc: PlaylistService = Depends(get_playlist_service),  # noqa: B008
) -> PaginatedResponse[PlaylistSummary]:
    """List playlists with optional source filter and cursor pagination."""
    page = await svc.list_all(limit=limit, cursor=cursor, source=source)
    return PaginatedResponse[PlaylistSummary](
        items=[svc.to_summary(p) for p in page.items],
        next_cursor=page.next_cursor,
        total=page.total,
    )


@tool(tags={ToolCategory.CORE.value}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def get_playlist(
    id: int | None = None,
    query: str | None = None,
    include_tracks: bool = False,
    svc: PlaylistService = Depends(get_playlist_service),  # noqa: B008
    track_svc: TrackService = Depends(get_track_service),  # noqa: B008
) -> dict[str, Any]:
    """Get playlist details by id or name query. Optionally include tracks."""
    playlist = await resolve_entity(
        entity_id=id,
        query=query,
        entity_name="playlist",
        get_by_id=svc.get_by_id,
        search_by_query=svc.search_by_name,
    )

    response = svc.to_summary(playlist).model_dump()
    response["tracks"] = []

    if include_tracks and playlist.items:
        track_ids = [item.track_id for item in sorted(playlist.items, key=lambda i: i.sort_index)]
        artist_map = await track_svc.get_artist_names_batch(track_ids)
        for tid in track_ids:
            try:
                t, feat = await track_svc.get_with_features(tid)
                tracks_entry = track_svc.to_brief(
                    t, feat, artist_names=artist_map.get(tid)
                ).model_dump()
                response["tracks"].append(tracks_entry)
            except Exception:
                response["tracks"].append(
                    {"id": tid, "title": f"[unresolved track {tid}]", "error": True}
                )

    return response


@tool(tags={ToolCategory.CORE.value}, annotations=ANNOTATIONS_WRITE)
@map_domain_errors
async def manage_playlist(
    action: str,
    data: Any = None,
    track_refs: Any = None,
    positions: Any = None,
    svc: PlaylistService = Depends(get_playlist_service),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Manage playlists.

    ``action`` ∈ ``{create, update, delete, add_tracks, remove_tracks, reorder}``.
    """
    if action not in _PLAYLIST_ACTIONS:
        raise ToolError(f"Unknown action: {action}. Valid: {', '.join(sorted(_PLAYLIST_ACTIONS))}")

    data_dict = ensure_dict(data)
    track_refs_list = ensure_list(track_refs) or None
    positions_list = ensure_list(positions) or None

    if action == "create":
        if not data_dict or "name" not in data_dict:
            raise ToolError("data.name required for create")
        playlist = await svc.create(data_dict["name"], data_dict.get("source_of_truth", "local"))
        return svc.to_summary(playlist, track_count=0).model_dump()

    playlist_id = (data_dict or {}).get("id")
    if playlist_id is None:
        raise ToolError("data.id required")

    if action == "delete":
        deleted = await svc.delete(playlist_id)
        return {"deleted": deleted, "id": playlist_id}

    if action == "update":
        fields = {k: v for k, v in (data_dict or {}).items() if k != "id"}
        playlist = await svc.update(playlist_id, **fields)
        return svc.to_summary(playlist).model_dump()

    if action == "add_tracks":
        if not track_refs_list:
            raise ToolError("track_refs required for add_tracks")
        resolved_ids = await resolve_track_refs(track_refs_list, session)
        if not resolved_ids:
            raise ToolError("No track refs could be resolved to local DB IDs")
        new_count = await svc.add_tracks(playlist_id, resolved_ids)
        playlist = await svc.get_by_id(playlist_id)
        return svc.to_summary(playlist, track_count=new_count).model_dump()

    if action == "remove_tracks":
        if not positions_list:
            raise ToolError("positions required for remove_tracks")
        removed = 0
        for pos in positions_list:
            if await svc.remove_track(playlist_id, pos):
                removed += 1
        return {"removed": removed, "playlist_id": playlist_id}

    # action == "reorder"
    if not track_refs_list or not positions_list:
        raise ToolError("track_refs and positions required for reorder")
    playlist = await svc.reorder_tracks(playlist_id, track_refs_list, positions_list)
    return svc.to_summary(playlist).model_dump()
