"""Playlist tools — list, get, manage (3 tools, tag: core).

Thin wrappers calling :class:`PlaylistService` via ``Depends()``.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies import (
    get_db_session,
    get_playlist_service,
    get_track_service,
)
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE,
    ICON_PLAYLISTS,
    TOOL_META,
    ToolCategory,
    map_domain_errors,
    resolve_entity,
)
from app.controllers.tools._shared.entity_resolver import resolve_track_refs
from app.core.utils.parsing import ensure_dict, ensure_list
from app.schemas import PaginatedResponse, PlaylistSummary
from app.services.playlist_service import PlaylistService
from app.services.track_service import TrackService

PlaylistManageAction = Literal[
    "create", "update", "delete", "add_tracks", "remove_tracks", "reorder"
]


@tool(
    title="List Playlists",
    tags={ToolCategory.CORE.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_PLAYLISTS,
    meta=TOOL_META,
)
@map_domain_errors
async def list_playlists(
    source: Annotated[str | None, Field(description="Filter by playlist source of truth")] = None,
    limit: Annotated[int, Field(description="Page size", ge=1)] = 20,
    cursor: Annotated[
        str | None, Field(description="Pagination cursor from previous page")
    ] = None,
    svc: PlaylistService = Depends(get_playlist_service),  # noqa: B008
) -> PaginatedResponse[PlaylistSummary]:
    """Lists playlists with optional source filter and cursor pagination. Use when browsing playlists or fetching the next page of results."""
    page = await svc.list_all(limit=limit, cursor=cursor, source=source)
    return PaginatedResponse[PlaylistSummary](
        items=[svc.to_summary(p) for p in page.items],
        next_cursor=page.next_cursor,
        total=page.total,
    )


@tool(
    title="Get Playlist",
    tags={ToolCategory.CORE.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_PLAYLISTS,
    meta=TOOL_META,
)
@map_domain_errors
async def get_playlist(
    id: Annotated[int | None, Field(description="Local playlist ID")] = None,
    query: Annotated[str | None, Field(description="Resolve playlist by name query")] = None,
    include_tracks: Annotated[
        bool, Field(description="Include full track briefs in response")
    ] = False,
    svc: PlaylistService = Depends(get_playlist_service),  # noqa: B008
    track_svc: TrackService = Depends(get_track_service),  # noqa: B008
) -> dict[str, Any]:
    """Returns playlist details resolved by local id or name query, optionally with track briefs. Use when inspecting a playlist before editing tracks or exporting."""
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


@tool(
    title="Manage Playlist",
    tags={ToolCategory.CORE.value},
    annotations=ANNOTATIONS_WRITE,
    icons=ICON_PLAYLISTS,
    meta=TOOL_META,
)
@map_domain_errors
async def manage_playlist(
    action: Annotated[PlaylistManageAction, Field(description="Operation to perform")],
    data: Annotated[
        Any,
        Field(
            description="Dict with 'id' (required for most actions) and 'name' (for create/update)"
        ),
    ] = None,
    track_refs: Annotated[Any, Field(description="Track IDs or YM IDs to add/reorder")] = None,
    positions: Annotated[
        Any, Field(description="0-based positions for remove_tracks or reorder")
    ] = None,
    svc: PlaylistService = Depends(get_playlist_service),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Creates, updates, deletes, or changes track membership and order on a playlist. Use when curating playlist contents or metadata instead of read-only listing."""

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
