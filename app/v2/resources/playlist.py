"""Playlist-scoped resources.

URIs:
    local://playlists/{id}{?include_tracks}
    local://playlists/{id}/audit
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.resources import resource

from app.v2.domain.audit.rules import DEFAULT_AUDIT_RULES, run_audit_rules
from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.resources._shared import (
    ANNOTATIONS_READ_ONLY,
    RESOURCE_META,
    json_dump,
)
from app.v2.schemas.resource_views import PlaylistAuditView
from app.v2.server.di import get_uow
from app.v2.shared.errors import NotFoundError


@resource(
    "local://playlists/{id}{?include_tracks}",
    mime_type="application/json",
    tags={"core", "namespace:library", "entity:playlist", "view:playlist"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def playlist_view(
    id: int,
    include_tracks: bool = False,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Playlist view. ``include_tracks=true`` embeds ordered items."""
    pl = await uow.playlists.get(id)
    if pl is None:
        raise NotFoundError("playlist", id)
    payload: dict[str, Any] = {
        "id": pl.id,
        "name": getattr(pl, "name", None),
        "source_of_truth": getattr(pl, "source_of_truth", None),
        "parent_id": getattr(pl, "parent_id", None),
    }
    if include_tracks:
        get_items = getattr(uow.playlists, "get_items", None)
        items = await get_items(id) if get_items is not None else []
        payload["tracks"] = [
            {
                "track_id": it.track_id,
                "sort_index": getattr(it, "sort_index", None),
            }
            for it in items
        ]
    return json_dump(payload)


@resource(
    "local://playlists/{id}/audit",
    mime_type="application/json",
    tags={"core", "namespace:library", "entity:playlist", "view:audit"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def playlist_audit(
    id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Run the techno audit against every track in the playlist."""
    if await uow.playlists.get(id) is None:
        raise NotFoundError("playlist", id)
    get_items = getattr(uow.playlists, "get_items", None)
    items = await get_items(id) if get_items is not None else []
    track_ids = [it.track_id for it in items]
    feat_map = await uow.track_features.get_scoring_features_batch(track_ids)

    per_track: list[dict[str, Any]] = []
    passed = 0
    failed = 0
    for it in items:
        tid = it.track_id
        feat = feat_map.get(tid)
        if feat is None:
            per_track.append(
                {
                    "track_id": tid,
                    "passed": False,
                    "violations": ["no features"],
                }
            )
            failed += 1
            continue
        track = await uow.tracks.get(tid)
        title = getattr(track, "title", "") or ""
        issues = run_audit_rules(DEFAULT_AUDIT_RULES, tid, title, feat)
        violations = [iss.issue for iss in issues]
        ok = not violations
        per_track.append(
            {
                "track_id": tid,
                "passed": ok,
                "violations": violations,
            }
        )
        if ok:
            passed += 1
        else:
            failed += 1

    view = PlaylistAuditView(
        playlist_id=id,
        total_tracks=len(items),
        passed=passed,
        failed=failed,
        per_track=per_track,
    )
    return view.model_dump_json()
