"""Playlist tools — list, get, manage (3 tools, tag: core).

Thin wrappers calling PlaylistService via Depends().
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool

from app.mcp.dependencies import get_playlist_service, get_track_service
from app.services.playlist_service import PlaylistService
from app.services.track_service import TrackService


@tool(tags={"core"}, annotations={"readOnlyHint": True})
async def list_playlists(
    source: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    svc: PlaylistService = Depends(get_playlist_service),  # noqa: B008
) -> dict[str, Any]:
    """List playlists with optional source filter and cursor pagination."""
    page = await svc.list_all(limit=limit, cursor=cursor, source=source)
    return {
        "items": [svc.to_summary(p).model_dump() for p in page.items],
        "next_cursor": page.next_cursor,
        "total": page.total,
    }


@tool(tags={"core"}, annotations={"readOnlyHint": True})
async def get_playlist(
    id: int | None = None,
    query: str | None = None,
    include_tracks: bool = False,
    svc: PlaylistService = Depends(get_playlist_service),  # noqa: B008
    track_svc: TrackService = Depends(get_track_service),  # noqa: B008
) -> dict[str, Any]:
    """Get playlist details by id or name query. Optionally include tracks."""
    if id is None and query is None:
        raise ToolError("Provide id or query")

    if id is not None:
        playlist = await svc.get_by_id(id)
    else:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.mcp.dependencies import get_db_session
        from app.models.playlist import Playlist

        async with get_db_session() as session:
            stmt = (
                select(Playlist)
                .where(Playlist.name.ilike(f"%{query}%"))
                .options(selectinload(Playlist.items))
                .limit(1)
            )
            result = await session.execute(stmt)
            playlist = result.scalar_one_or_none()
            if playlist is None:
                raise ToolError("Playlist not found")

    response = svc.to_summary(playlist).model_dump()

    if include_tracks and playlist.items:
        track_ids = [item.track_id for item in sorted(playlist.items, key=lambda i: i.sort_index)]
        tracks = []
        for tid in track_ids:
            try:
                t, _ = await track_svc.get_with_features(tid)
                tracks.append(track_svc.to_brief(t).model_dump())
            except Exception:
                pass
        response["tracks"] = tracks

    return response


@tool(tags={"core"}, annotations={"readOnlyHint": False})
async def manage_playlist(
    action: str,
    data: Any = None,
    track_refs: Any = None,
    positions: Any = None,
    svc: PlaylistService = Depends(get_playlist_service),  # noqa: B008
) -> dict[str, Any]:
    """Manage playlists. action: create|update|delete|add_tracks|remove_tracks|reorder."""
    from app.core.parsing import ensure_dict, ensure_list

    data = ensure_dict(data)
    track_refs = ensure_list(track_refs) or None
    positions = ensure_list(positions) or None
    valid = ("create", "update", "delete", "add_tracks", "remove_tracks", "reorder")
    if action not in valid:
        raise ToolError(f"Unknown action: {action}. Valid: {', '.join(valid)}")

    if action == "create":
        if not data or "name" not in data:
            raise ToolError("data.name required for create")
        playlist = await svc.create(data["name"], data.get("source_of_truth", "local"))
        return svc.to_summary(playlist, track_count=0).model_dump()

    playlist_id = (data or {}).get("id")
    if playlist_id is None:
        raise ToolError("data.id required")

    if action == "delete":
        deleted = await svc.delete(playlist_id)
        return {"deleted": deleted, "id": playlist_id}

    if action == "update":
        fields = {k: v for k, v in (data or {}).items() if k != "id"}
        playlist = await svc.update(playlist_id, **fields)
        return svc.to_summary(playlist).model_dump()

    if action == "add_tracks":
        if not track_refs:
            raise ToolError("track_refs required for add_tracks")
        new_count = await svc.add_tracks(playlist_id, track_refs)
        playlist = await svc.get_by_id(playlist_id)
        return svc.to_summary(playlist, track_count=new_count).model_dump()

    if action == "remove_tracks":
        if not positions:
            raise ToolError("positions required for remove_tracks")
        removed = sum(1 for pos in positions if await svc.remove_track(playlist_id, pos))
        return {"removed": removed, "playlist_id": playlist_id}

    if action == "reorder":
        if not track_refs or not positions:
            raise ToolError("track_refs and positions required for reorder")
        from app.mcp.dependencies import get_db_session
        from app.repositories.playlist import PlaylistRepository

        async with get_db_session() as session:
            playlist = await svc.get_by_id(playlist_id)
            for item in list(playlist.items):
                await session.delete(item)
            await session.flush()
        async with get_db_session() as session:
            repo = PlaylistRepository(session)
            for tid, pos in zip(track_refs, positions, strict=False):
                await repo.add_track(playlist_id, tid, pos)
        playlist = await svc.get_by_id(playlist_id)
        return svc.to_summary(playlist).model_dump()

    raise ToolError("Unreachable")
