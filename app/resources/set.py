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

from app.repositories.unit_of_work import UnitOfWork
from app.resources._shared import (
    ANNOTATIONS_READ_ONLY,
    RESOURCE_META,
    json_dump,
)
from app.schemas.resource_views import (
    SetCheatsheetView,
    SetCompareView,
    SetNarrativeView,
    SetReviewView,
    SetSummaryView,
    SetTracksView,
    SetTransitionsView,
)
from app.server.di import get_uow
from app.shared.errors import NotFoundError, ValidationError

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
        # Smoke test 2026-05-07 (mirrors ui_set_view fix): pre-v1.3 sets
        # have no rows in ``transitions`` for their pairs, so every entry
        # used to render as ``overall=null`` / ``hard_reject=null``. Fall
        # back to live ``TransitionScorer`` (~1 ms per pair, pure
        # compute) when the persisted row is missing.
        feat_map = await uow.track_features.get_scoring_features_batch(ordered)
        scorer: Any = None
        transitions: list[dict[str, Any]] = []
        for pos, (a, b) in enumerate(itertools.pairwise(ordered)):
            t = await _get_transition(uow, a, b)
            overall = getattr(t, "overall_quality", None) if t else None
            hard_reject = bool(getattr(t, "hard_reject", False)) if t else None
            if overall is None and hard_reject is None:
                feat_a = feat_map.get(a)
                feat_b = feat_map.get(b)
                if feat_a is not None and feat_b is not None:
                    if scorer is None:
                        from app.domain.transition.scorer import TransitionScorer

                        scorer = TransitionScorer()
                    live = scorer.score(feat_a, feat_b)
                    overall = live.overall
                    hard_reject = live.hard_reject
            transitions.append(
                {
                    "position": pos + 1,
                    "from_track_id": a,
                    "to_track_id": b,
                    "overall": overall,
                    "hard_reject": hard_reject,
                }
            )
        return SetTransitionsView(
            set_id=s.id, version_id=latest.id, transitions=transitions
        ).model_dump_json()

    # view == "full"
    summary_json = await set_view_resource(id=id, view="summary", uow=uow)
    tracks_json = await set_view_resource(id=id, view="tracks", uow=uow)
    transitions_json = await set_view_resource(id=id, view="transitions", uow=uow)
    return json_dump(
        {
            "summary": _json.loads(summary_json),
            "tracks": _json.loads(tracks_json),
            "transitions": _json.loads(transitions_json),
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
    ordered_ids = [it.track_id for it in items]
    features = await uow.track_features.get_scoring_features_batch(ordered_ids)
    pairs = list(itertools.pairwise(ordered_ids))
    batch_get = getattr(uow.transitions, "get_pairs_batch", None)
    transitions = await batch_get(pairs) if batch_get is not None else {}

    from app.domain.camelot.wheel import key_code_to_camelot

    def _camelot(key_code: int | None) -> str | None:
        if key_code is None:
            return None
        try:
            return key_code_to_camelot(key_code)
        except ValueError:
            return None

    lines: list[dict[str, Any]] = []
    for index, it in enumerate(items):
        track = await uow.tracks.get(it.track_id)
        feat = features.get(it.track_id)
        canonical_key_code = getattr(feat, "key_code", None) if feat else None
        audio_key_code = getattr(feat, "audio_key_code", None) if feat else None
        next_transition = None
        if index + 1 < len(items):
            next_track_id = items[index + 1].track_id
            transition = transitions.get((it.track_id, next_track_id))
            if transition is not None:
                next_transition = {
                    "to_track_id": next_track_id,
                    "overall": getattr(transition, "overall_quality", None),
                    "fx_type": getattr(transition, "fx_type", None),
                    "bars": getattr(transition, "transition_bars", None),
                    "hard_reject": bool(getattr(transition, "hard_reject", False)),
                }
        lines.append(
            {
                "position": getattr(it, "sort_index", None),
                "track_id": it.track_id,
                "title": getattr(track, "title", None) if track else None,
                "bpm": getattr(feat, "bpm", None) if feat else None,
                "bpm_source": getattr(feat, "bpm_source", None) if feat else None,
                "audio_bpm": getattr(feat, "audio_bpm", None) if feat else None,
                "beatport_bpm": getattr(feat, "beatport_bpm", None) if feat else None,
                "key": _camelot(canonical_key_code),
                "key_code": canonical_key_code,
                "key_source": getattr(feat, "key_source", None) if feat else None,
                "audio_key": _camelot(audio_key_code),
                "audio_key_code": audio_key_code,
                "audio_key_confidence": (
                    getattr(feat, "audio_key_confidence", None) if feat else None
                ),
                "beatport_key": getattr(feat, "beatport_key", None) if feat else None,
                "beatport_camelot": (getattr(feat, "beatport_camelot", None) if feat else None),
                "beatport_confidence": (
                    getattr(feat, "beatport_confidence", None) if feat else None
                ),
                "key_agreement": (
                    canonical_key_code == audio_key_code
                    if canonical_key_code is not None and audio_key_code is not None
                    else None
                ),
                "energy": getattr(feat, "integrated_lufs", None) if feat else None,
                "in_section_id": getattr(it, "in_section_id", None),
                "out_section_id": getattr(it, "out_section_id", None),
                "mix_in_point_ms": getattr(it, "mix_in_point_ms", None),
                "mix_out_point_ms": getattr(it, "mix_out_point_ms", None),
                "next_transition": next_transition,
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
    "local://sets/{id}/review{?version}",
    mime_type="application/json",
    tags={"core", "namespace:library", "entity:set", "view:review"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def set_review(
    id: int,
    version: int | None = None,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Aggregate transition issues: weak scores, hard conflicts, overall quality.

    ``version`` pins a specific set_version; default is the latest one —
    which is NOT necessarily the chosen/best version when several exist.
    """
    if await uow.sets.get(id) is None:
        raise NotFoundError("set", id)
    if version is not None:
        latest = await uow.set_versions.get(version)
        if latest is None or getattr(latest, "set_id", None) != id:
            raise NotFoundError("set_version", version)
    else:
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
    # Audit iter 58 (T-56):
    # 1. Same-version compare (``a == b``) used to return a trivial
    #    ``delta=0, changed_positions=[]`` row. That's not a comparison
    #    — reject it explicitly so callers don't think "no diff" hides
    #    a real change.
    # 2. Cross-set ids leaked a misleading ``set_version not found: 3``
    #    even though version 3 EXISTS — just in a different set. Now
    #    we surface the actual set mismatch.
    # 3. ``zip(items_a, items_b, strict=False)`` silently dropped tail
    #    positions when the two versions had different lengths. Switch
    #    to length-aware iteration so any tail difference is also
    #    counted as ``changed``.
    from app.shared.errors import ValidationError

    if a == b:
        raise ValidationError(
            f"compare requires two distinct version ids; got {a} for both",
            details={"set_id": id, "a": a, "b": b},
        )
    va = await uow.set_versions.get(a)
    vb = await uow.set_versions.get(b)
    if va is None:
        raise NotFoundError("set_version", a)
    if getattr(va, "set_id", None) != id:
        raise NotFoundError(
            "set_version",
            f"{a} (belongs to set {va.set_id}, not {id})",
        )
    if vb is None:
        raise NotFoundError("set_version", b)
    if getattr(vb, "set_id", None) != id:
        raise NotFoundError(
            "set_version",
            f"{b} (belongs to set {vb.set_id}, not {id})",
        )
    items_a = sorted(
        await _get_version_items(uow, va.id),
        key=lambda i: getattr(i, "sort_index", 0),
    )
    items_b = sorted(
        await _get_version_items(uow, vb.id),
        key=lambda i: getattr(i, "sort_index", 0),
    )
    changed: list[int] = []
    max_len = max(len(items_a), len(items_b))
    for i in range(max_len):
        track_a = items_a[i].track_id if i < len(items_a) else None
        track_b = items_b[i].track_id if i < len(items_b) else None
        if track_a != track_b:
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
