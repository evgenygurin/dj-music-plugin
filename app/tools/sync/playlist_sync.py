"""playlist_sync — bidirectional sync between local playlist and platform playlist."""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import BaseModel, Field

from app.registry.provider import ProviderRegistry
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.tool_responses import PlaylistSyncResult
from app.server.di import get_provider_registry, get_uow
from app.shared.errors import NotFoundError, ValidationError


class ConflictResolution(BaseModel):
    action: Literal["local_wins", "remote_wins", "merge", "abort"]


@tool(
    name="playlist_sync",
    tags={"namespace:sync", "write", "sync"},
    annotations={
        "readOnlyHint": False,
        "openWorldHint": True,
        "idempotentHint": False,
    },
    description=(
        "Sync a local playlist with its platform counterpart. direction=pull "
        "(platform→local), push (local→platform), or diff (report-only). "
        "Use dry_run=true to preview."
    ),
    meta={"timeout_s": 180.0},
    timeout=180.0,
)
async def playlist_sync(
    playlist_id: Annotated[int, Field(ge=1, description="Local playlist ID")],
    direction: Annotated[
        Literal["pull", "push", "diff"], Field(description="Sync direction")
    ] = "diff",
    source: Annotated[
        str, Field(description="Provider name (matches platform_ids key)")
    ] = "yandex",
    dry_run: Annotated[bool, Field(description="Preview without applying")] = False,
    uow: UnitOfWork = Depends(get_uow),
    registry: ProviderRegistry = Depends(get_provider_registry),
    ctx: Context = CurrentContext(),
) -> PlaylistSyncResult:
    pl = await uow.playlists.get(playlist_id)
    if pl is None:
        raise NotFoundError("playlist", playlist_id)

    platform_map = json.loads(getattr(pl, "platform_ids", None) or "{}")
    remote_id = platform_map.get(source)
    if remote_id is None:
        raise ValidationError(
            f"playlist {playlist_id} has no {source} platform_id",
            details={"platform_ids": platform_map},
        )

    provider = registry.get(source)
    remote = await provider.read("playlist", id=remote_id, params={})

    local_track_ids: list[int] = [item.track_id for item in getattr(pl, "items", []) or []]
    remote_tracks = remote.get("tracks") or []
    remote_ext_ids: list[str] = [str(t.get("id")) for t in remote_tracks if t.get("id")]

    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    if direction == "pull":
        existing = await uow.tracks.batch_get_by_provider_ids(source, remote_ext_ids)
        for ext_id in remote_ext_ids:
            if ext_id in existing:
                skipped.append({"external_id": ext_id, "reason": "already local"})
                continue
            applied.append({"op": "pull", "external_id": ext_id})

    elif direction == "push":
        known_remote = {str(t.get("id")) for t in remote_tracks}
        for tid in local_track_ids:
            ext = await uow.tracks.get_provider_id(tid, source)
            if ext is None:
                conflicts.append({"track_id": tid, "reason": "no provider id"})
                continue
            if ext in known_remote:
                skipped.append({"track_id": tid, "reason": "already on remote"})
                continue
            applied.append({"op": "push", "track_id": tid, "external_id": ext})
            if not dry_run:
                await provider.write(
                    "playlist",
                    operation="add_tracks",
                    params={
                        "playlist_id": remote_id,
                        "track_ids": [ext],
                        "revision": int(remote.get("revision", 0)),
                        "at": 0,
                    },
                )

    else:  # diff
        known_remote = {str(t.get("id")) for t in remote_tracks}
        local_ext_ids: set[str] = set()
        for tid in local_track_ids:
            ext = await uow.tracks.get_provider_id(tid, source)
            if ext is None:
                conflicts.append({"track_id": tid, "reason": "no provider id"})
                continue
            local_ext_ids.add(ext)
            if ext not in known_remote:
                applied.append({"op": "local_only", "track_id": tid, "external_id": ext})
        for ext_id in remote_ext_ids:
            if ext_id not in local_ext_ids:
                applied.append({"op": "remote_only", "ext_id": ext_id})

    return PlaylistSyncResult(
        playlist_id=playlist_id,
        direction=direction,
        applied=applied,
        skipped=skipped,
        conflicts=conflicts,
    )
