"""Set-scoped resources.

URIs:
    local://sets/{id}/{view}                     view ∈ {summary,tracks,transitions,full}
    local://sets/{id}/cheatsheet{?version}
    local://sets/{id}/narrative
    local://sets/{id}/review
    local://sets/{id}/versions/compare/{a}/{b}
"""

from __future__ import annotations

import itertools
import json as _json
from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.resources import resource

from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.resources._shared import (
    ANNOTATIONS_READ_ONLY,
    RESOURCE_META,
    json_dump,
)
from app.v2.schemas.resource_views import (
    SetCheatsheetView,
    SetCompareView,
    SetNarrativeView,
    SetReviewView,
    SetSummaryView,
    SetTracksView,
    SetTransitionsView,
)
from app.v2.server.di import get_uow
from app.v2.shared.errors import NotFoundError, ValidationError

_ALLOWED_VIEWS = frozenset({"summary", "tracks", "transitions", "full"})


async def _get_latest_version(uow: UnitOfWork, set_id: int) -> Any | None:
    """Defensive accessor for latest set version."""
    fn = getattr(uow.set_versions, "get_latest", None) or getattr(
        uow.set_versions, "latest_version", None
    )
    if fn is None:
        return None
    return await fn(set_id)


async def _get_version_items(uow: UnitOfWork, version_id: int) -> list[Any]:
    fn = getattr(uow.set_versions, "get_items", None)
    if fn is None:
        return []
    return list(await fn(version_id))


async def _count_versions(uow: UnitOfWork, set_id: int) -> int:
    fn = getattr(uow.set_versions, "count_for_set", None)
    if fn is None:
        return 0
    return int(await fn(set_id))


async def _get_transition(uow: UnitOfWork, a: int, b: int) -> Any | None:
    fn = getattr(uow.transitions, "get_by_pair", None)
    if fn is None:
        return None
    return await fn(a, b)


async def _get_features_for(uow: UnitOfWork, track_id: int) -> Any | None:
    feats = await uow.track_features.get_scoring_features_batch([track_id])
    return feats.get(track_id)


@resource(
    "local://sets/{id}/{view}",
    mime_type="application/json",
    tags={"core", "namespace:library", "entity:set"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def set_view_resource(
    id: int,
    view: str,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Set view: summary | tracks | transitions | full."""
    if view not in _ALLOWED_VIEWS:
        raise ValidationError(
            f"unknown set view {view!r}",
            details={"allowed": sorted(_ALLOWED_VIEWS)},
        )
    s = await uow.sets.get(id)
    if s is None:
        raise NotFoundError("set", id)
    latest = await _get_latest_version(uow, id)

    if view == "summary":
        v = SetSummaryView(
            set_id=s.id,
            name=getattr(s, "name", "") or "",
            template_name=getattr(s, "template_name", None),
            version_count=await _count_versions(uow, id),
            latest_version_id=latest.id if latest else None,
            latest_quality_score=getattr(latest, "quality_score", None) if latest else None,
        )
        return v.model_dump_json()

    if view == "tracks":
        if latest is None:
            return SetTracksView(set_id=s.id, version_id=0, tracks=[]).model_dump_json()
        items = sorted(
            await _get_version_items(uow, latest.id),
            key=lambda i: getattr(i, "sort_index", 0),
        )
        tracks: list[dict[str, Any]] = []
        for it in items:
            track = await uow.tracks.get(it.track_id)
            tracks.append(
                {
                    "position": getattr(it, "sort_index", None),
                    "track_id": it.track_id,
                    "title": getattr(track, "title", None) if track else None,
                    "pinned": bool(getattr(it, "pinned", False)),
                }
            )
        return SetTracksView(set_id=s.id, version_id=latest.id, tracks=tracks).model_dump_json()

    if view == "transitions":
        if latest is None:
            return SetTransitionsView(set_id=s.id, version_id=0, transitions=[]).model_dump_json()
        items = sorted(
            await _get_version_items(uow, latest.id),
            key=lambda i: getattr(i, "sort_index", 0),
        )
        ordered = [it.track_id for it in items]
        transitions: list[dict[str, Any]] = []
        for pos, (a, b) in enumerate(itertools.pairwise(ordered)):
            t = await _get_transition(uow, a, b)
            transitions.append(
                {
                    "position": pos + 1,
                    "from_track_id": a,
                    "to_track_id": b,
                    "overall": getattr(t, "overall_quality", None) if t else None,
                    "hard_reject": bool(getattr(t, "hard_reject", False)) if t else None,
                }
            )
        return SetTransitionsView(
            set_id=s.id, version_id=latest.id, transitions=transitions
        ).model_dump_json()

    # view == "full"
    summary = await set_view_resource(id=id, view="summary", uow=uow)
    tracks = await set_view_resource(id=id, view="tracks", uow=uow)
    transitions = await set_view_resource(id=id, view="transitions", uow=uow)
    return json_dump(
        {
            "summary": _json.loads(summary),
            "tracks": _json.loads(tracks),
            "transitions": _json.loads(transitions),
        }
    )


@resource(
    "local://sets/{id}/cheatsheet{?version}",
    mime_type="application/json",
    tags={"core", "namespace:library", "entity:set", "view:cheatsheet"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def set_cheatsheet(
    id: int,
    version: int | None = None,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """One-line-per-track summary for the DJ booth."""
    if version is not None:
        ver = await uow.set_versions.get(version)
    else:
        ver = await _get_latest_version(uow, id)
    if ver is None or getattr(ver, "set_id", None) != id:
        raise NotFoundError("set_version", version or f"latest(set={id})")
    items = sorted(
        await _get_version_items(uow, ver.id),
        key=lambda i: getattr(i, "sort_index", 0),
    )
    lines: list[dict[str, Any]] = []
    for it in items:
        track = await uow.tracks.get(it.track_id)
        feat = await _get_features_for(uow, it.track_id)
        lines.append(
            {
                "position": getattr(it, "sort_index", None),
                "title": getattr(track, "title", None) if track else None,
                "bpm": getattr(feat, "bpm", None) if feat else None,
                "key": getattr(feat, "key_code", None) if feat else None,
                "energy": getattr(feat, "integrated_lufs", None) if feat else None,
            }
        )
    return SetCheatsheetView(set_id=id, version_id=ver.id, lines=lines).model_dump_json()


@resource(
    "local://sets/{id}/narrative",
    mime_type="application/json",
    tags={"core", "namespace:library", "entity:set", "view:narrative"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def set_narrative(
    id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Human-readable arc narrative for the current (latest) version."""
    s = await uow.sets.get(id)
    if s is None:
        raise NotFoundError("set", id)
    latest = await _get_latest_version(uow, id)
    if latest is None:
        return SetNarrativeView(set_id=id, version_id=0, narrative="", phases=[]).model_dump_json()
    items = await _get_version_items(uow, latest.id)
    if not items:
        return SetNarrativeView(
            set_id=id, version_id=latest.id, narrative="(empty)", phases=[]
        ).model_dump_json()
    n = len(items)
    phases = [
        {"label": "warm_up", "start": 0, "end": max(0, n // 3 - 1)},
        {"label": "peak", "start": n // 3, "end": max(0, 2 * n // 3 - 1)},
        {"label": "close", "start": 2 * n // 3, "end": n - 1},
    ]
    template_name = getattr(s, "template_name", None) or "ad-hoc"
    narrative = f"{n} tracks across warm_up/peak/close. Template {template_name}."
    return SetNarrativeView(
        set_id=id,
        version_id=latest.id,
        narrative=narrative,
        phases=phases,
    ).model_dump_json()


@resource(
    "local://sets/{id}/review",
    mime_type="application/json",
    tags={"core", "namespace:library", "entity:set", "view:review"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def set_review(
    id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Aggregate transition issues: weak scores, hard conflicts, overall quality."""
    if await uow.sets.get(id) is None:
        raise NotFoundError("set", id)
    latest = await _get_latest_version(uow, id)
    if latest is None:
        raise NotFoundError("set_version", f"latest(set={id})")
    items = sorted(
        await _get_version_items(uow, latest.id),
        key=lambda i: getattr(i, "sort_index", 0),
    )
    weak: list[dict[str, Any]] = []
    hard: list[dict[str, Any]] = []
    for pos, (a, b) in enumerate(itertools.pairwise(items)):
        t = await _get_transition(uow, a.track_id, b.track_id)
        if t is None:
            continue
        if bool(getattr(t, "hard_reject", False)):
            hard.append(
                {
                    "position": pos + 1,
                    "from_track_id": a.track_id,
                    "to_track_id": b.track_id,
                    "reason": getattr(t, "reject_reason", None),
                }
            )
        elif (getattr(t, "overall_quality", 0) or 0) < 0.5:
            weak.append(
                {
                    "position": pos + 1,
                    "score": getattr(t, "overall_quality", None),
                    "reason": "below 0.5 overall",
                }
            )
    return SetReviewView(
        set_id=id,
        version_id=latest.id,
        quality_score=getattr(latest, "quality_score", 0.0) or 0.0,
        weak_transitions=weak,
        hard_conflicts=hard,
    ).model_dump_json()


@resource(
    "local://sets/{id}/versions/compare/{a}/{b}",
    mime_type="application/json",
    tags={"core", "namespace:library", "entity:set_version", "view:compare"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def set_versions_compare(
    id: int,
    a: int,
    b: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Compare two versions of the same set: quality delta + changed positions."""
    va = await uow.set_versions.get(a)
    vb = await uow.set_versions.get(b)
    if va is None or getattr(va, "set_id", None) != id:
        raise NotFoundError("set_version", a)
    if vb is None or getattr(vb, "set_id", None) != id:
        raise NotFoundError("set_version", b)
    items_a = sorted(
        await _get_version_items(uow, va.id),
        key=lambda i: getattr(i, "sort_index", 0),
    )
    items_b = sorted(
        await _get_version_items(uow, vb.id),
        key=lambda i: getattr(i, "sort_index", 0),
    )
    changed: list[int] = []
    for i, (x, y) in enumerate(zip(items_a, items_b, strict=False)):
        if x.track_id != y.track_id:
            changed.append(i + 1)
    qa = getattr(va, "quality_score", None)
    qb = getattr(vb, "quality_score", None)
    return SetCompareView(
        set_id=id,
        version_a={"id": va.id, "quality_score": qa},
        version_b={"id": vb.id, "quality_score": qb},
        delta=(qb or 0.0) - (qa or 0.0),
        changed_positions=changed,
    ).model_dump_json()
