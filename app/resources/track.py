"""Track-scoped resources.

URIs:
    local://tracks/{id}
    local://tracks/{id}/features
    local://tracks/{id}/audit
    local://tracks/{id}/suggest_next{?limit,energy_direction}
    local://tracks/{id}/suggest_replacement/{set_id}/{position}
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.resources import resource

from app.domain.audit.rules import DEFAULT_AUDIT_RULES, run_audit_rules
from app.repositories.unit_of_work import UnitOfWork
from app.resources._shared import (
    ANNOTATIONS_READ_ONLY,
    RESOURCE_META,
    json_dump,
)
from app.schemas.resource_views import (
    SuggestNextView,
    SuggestReplacementView,
    TrackAuditView,
)
from app.schemas.track import TrackView
from app.server.di import get_uow
from app.shared.errors import NotFoundError


@resource(
    "local://tracks/{id}",
    mime_type="application/json",
    tags={"core", "namespace:library", "entity:track", "view:track"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def track_view(
    id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Single-track view (core fields + relations projection)."""
    row = await uow.tracks.get(id)
    if row is None:
        raise NotFoundError("track", id)
    return TrackView.model_validate(row).model_dump_json()


@resource(
    "local://tracks/{id}/features",
    mime_type="application/json",
    tags={"core", "namespace:library", "entity:track_features", "view:features"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def track_features(
    id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Audio features for a track (bpm, key, loudness, energy, spectral, rhythm)."""
    feat = await _get_features(uow, id)
    if feat is None:
        raise NotFoundError("track_features", id)
    return json_dump(_track_features_payload(id, feat))


@resource(
    "local://tracks/{id}/audit",
    mime_type="application/json",
    tags={"core", "namespace:library", "entity:track", "view:audit"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def track_audit(
    id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Run the techno audit rules against a single track."""
    track = await uow.tracks.get(id)
    if track is None:
        raise NotFoundError("track", id)
    feat = await _get_features(uow, id)
    if feat is None:
        raise NotFoundError("track_features", id)
    title = getattr(track, "title", "") or ""
    issues = run_audit_rules(DEFAULT_AUDIT_RULES, id, title, feat)
    criteria_checked = len(DEFAULT_AUDIT_RULES)
    violations = [iss.issue for iss in issues]
    # Score: fraction of rules that did NOT raise an issue.
    score = max(
        0.0,
        min(
            1.0,
            (criteria_checked - len(violations)) / float(criteria_checked or 1),
        ),
    )
    view = TrackAuditView(
        track_id=id,
        passed=not violations,
        violations=violations,
        score=score,
        criteria_checked=criteria_checked,
    )
    return view.model_dump_json()


@resource(
    "local://tracks/{id}/suggest_next{?limit,energy_direction}",
    mime_type="application/json",
    tags={"core", "namespace:reasoning", "view:suggest_next"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def track_suggest_next(
    id: int,
    limit: int = 10,
    energy_direction: str | None = None,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Suggest ``limit`` next-track candidates for a free-standing track.

    ``energy_direction`` ∈ {``up``, ``down``, ``flat``, ``None``}.
    """
    if await uow.tracks.get(id) is None:
        raise NotFoundError("track", id)
    candidates = await _compute_suggest_next(
        uow, track_id=id, limit=limit, direction=energy_direction
    )
    view = SuggestNextView(
        from_track_id=id,
        limit=limit,
        energy_direction=energy_direction,
        candidates=candidates,
    )
    return view.model_dump_json()


@resource(
    "local://tracks/{id}/suggest_replacement/{set_id}/{position}",
    mime_type="application/json",
    tags={"core", "namespace:reasoning", "view:suggest_replacement"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def track_suggest_replacement(
    id: int,
    set_id: int,
    position: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Suggest replacements for ``track_id=id`` at ``position`` in ``set_id``."""
    if await uow.sets.get(set_id) is None:
        raise NotFoundError("set", set_id)
    candidates = await _compute_suggest_replacement(
        uow, set_id=set_id, position=position, removed_track_id=id
    )
    view = SuggestReplacementView(
        set_id=set_id,
        position=position,
        removed_track_id=id,
        candidates=candidates,
    )
    return view.model_dump_json()


# ── internal helpers (no side effects, no I/O beyond `uow`) ────


async def _get_features(uow: UnitOfWork, track_id: int) -> Any | None:
    """Load a single track's features via batch repo (Phase 4 surface)."""
    feats = await uow.track_features.get_scoring_features_batch([track_id])
    return feats.get(track_id)


def _track_features_payload(track_id: int, feat: object) -> dict[str, Any]:
    """Project the subset of features published on this endpoint.

    Kept small and explicit; do NOT dump the ORM row directly — that would
    leak SQLAlchemy state.
    """
    return {
        "track_id": track_id,
        "bpm": getattr(feat, "bpm", None),
        "bpm_confidence": getattr(feat, "bpm_confidence", None),
        "key_code": getattr(feat, "key_code", None),
        "integrated_lufs": getattr(feat, "integrated_lufs", None),
        "energy_mean": getattr(feat, "energy_mean", None),
        "kick_prominence": getattr(feat, "kick_prominence", None),
        "onset_rate": getattr(feat, "onset_rate", None),
        "spectral_centroid_hz": getattr(feat, "spectral_centroid_hz", None),
        "analysis_level": getattr(feat, "analysis_level", None),
        "mood": getattr(feat, "mood", None),
        "mood_confidence": getattr(feat, "mood_confidence", None),
    }


async def _compute_suggest_next(
    uow: UnitOfWork,
    *,
    track_id: int,
    limit: int,
    direction: str | None,
) -> list[dict[str, Any]]:
    """Compute next-track candidates using the in-DB transition+features data.

    Phase 5 will promote this to a richer strategy; for now it returns an
    empty list when ``list_from`` is not yet available on the transition repo.
    """
    list_from = getattr(uow.transitions, "list_from", None)
    if list_from is None:
        return []
    rows = await list_from(track_id, limit=limit * 3)
    out: list[dict[str, Any]] = []
    feat_ids = [r.to_track_id for r in rows]
    feat_map = await uow.track_features.get_scoring_features_batch(feat_ids)
    for r in rows:
        feat_to = feat_map.get(r.to_track_id)
        if feat_to is None:
            continue
        if direction == "up" and (feat_to.energy_mean or 0) <= 0:
            continue
        if direction == "down" and (feat_to.energy_mean or 0) >= 1:
            continue
        track = await uow.tracks.get(r.to_track_id)
        out.append(
            {
                "track_id": r.to_track_id,
                "title": track.title if track else "",
                "score": r.overall_quality,
                "bpm": feat_to.bpm,
                "key": feat_to.key_code,
            }
        )
        if len(out) >= limit:
            break
    return out


async def _compute_suggest_replacement(
    uow: UnitOfWork,
    *,
    set_id: int,
    position: int,
    removed_track_id: int,
) -> list[dict[str, Any]]:
    """Candidate replacements: tracks with similar BPM/energy to removed_track_id,
    excluding tracks already in the set's latest version.

    Falls back to an empty candidate list when the underlying repository
    methods (``latest_version``, ``search_by_bpm_range``) are not yet
    wired — Phase 5 completes the surface.
    """
    latest_version = getattr(uow.set_versions, "latest_version", None)
    if latest_version is None:
        return []
    ver = await latest_version(set_id)
    if ver is None:
        return []
    items = await uow.set_versions.get_items(ver.id)
    excluded = {it.track_id for it in items}
    target_map = await uow.track_features.get_scoring_features_batch([removed_track_id])
    target_feat = target_map.get(removed_track_id)
    if target_feat is None:
        return []
    bpm = target_feat.bpm or 0.0
    search_by_bpm_range = getattr(uow.tracks, "search_by_bpm_range", None)
    if search_by_bpm_range is None:
        return []
    candidates = await search_by_bpm_range(
        bpm_min=bpm - 2.0, bpm_max=bpm + 2.0, exclude_ids=excluded, limit=10
    )
    return [
        {
            "track_id": t.id,
            "title": t.title,
            "score": 0.0,
            "reason": f"bpm within 2 of {bpm}",
        }
        for t in candidates
    ]
