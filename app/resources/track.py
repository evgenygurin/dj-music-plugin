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
from app.shared.errors import NotFoundError, ValidationError


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
    """Single-track view (core fields + relations projection).

    Resolves ``primary_artist_name`` via the repository (audit O-1):
    ``TrackView.from_attributes`` alone returned ``null`` because the
    field is a derived value over the ``track_artists`` relationship,
    not a plain ORM column.
    """
    row = await uow.tracks.get(id)
    if row is None:
        raise NotFoundError("track", id)
    view = TrackView.model_validate(row)
    payload = view.model_dump()
    payload["primary_artist_name"] = await uow.tracks.get_primary_artist_name(id)
    return json_dump(payload)


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
    Empty ``candidates`` is paired with a ``reason`` string explaining
    the cause (audit O-3), so consumers can distinguish "no historical
    transitions for this track" from "the energy filter rejected
    everything".
    """
    # Resources don't get Pydantic Field validation the way @tool params do —
    # the URI template just hands a raw string through. Bogus values
    # (``energy_direction=sideways``) used to fall through ``direction in
    # {"up", "down"}`` and silently behave like ``None``, which masked typos.
    allowed_directions = {"up", "down", "flat", None}
    if energy_direction not in allowed_directions:
        raise ValidationError(
            f"invalid energy_direction {energy_direction!r}; allowed: ['up', 'down', 'flat', null]"
        )
    if await uow.tracks.get(id) is None:
        raise NotFoundError("track", id)
    candidates, reason = await _compute_suggest_next(
        uow, track_id=id, limit=limit, direction=energy_direction
    )
    view = SuggestNextView(
        from_track_id=id,
        limit=limit,
        energy_direction=energy_direction,
        candidates=candidates,
        reason=reason,
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
    """Suggest replacements for ``track_id=id`` at ``position`` in ``set_id``.

    Empty ``candidates`` is paired with a ``reason`` string (audit O-3)
    so consumers can distinguish "set has no version yet" from "no
    track within ±2 BPM of the removed one".
    """
    if await uow.sets.get(set_id) is None:
        raise NotFoundError("set", set_id)
    candidates, reason = await _compute_suggest_replacement(
        uow, set_id=set_id, position=position, removed_track_id=id
    )
    view = SuggestReplacementView(
        set_id=set_id,
        position=position,
        removed_track_id=id,
        candidates=candidates,
        reason=reason,
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
        "mood_source": getattr(feat, "mood_source", None),
        "beatport_genre": getattr(feat, "beatport_genre", None),
        "beatport_sub_genre": getattr(feat, "beatport_sub_genre", None),
        "beatport_confidence": getattr(feat, "beatport_confidence", None),
    }


async def _compute_suggest_next(
    uow: UnitOfWork,
    *,
    track_id: int,
    limit: int,
    direction: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Compute next-track candidates using the in-DB transition+features data.

    Returns ``(candidates, reason)`` — ``reason`` is ``None`` on success
    (or empty for legitimate-no-data) and a short string when the empty
    result has a structural cause the caller should know about.
    """
    list_from = getattr(uow.transitions, "list_from", None)
    if list_from is None:
        return [], "transitions repository does not expose list_from yet"
    rows = await list_from(track_id, limit=limit * 3)
    if not rows:
        return [], "no historical transitions logged for this track"
    out: list[dict[str, Any]] = []
    feat_ids = [r.to_track_id for r in rows]
    # Audit iter 43 (T-41): the prior energy_direction filter compared
    # ``candidate.energy_mean`` against absolute thresholds (``<= 0``
    # for "up", ``>= 1`` for "down"). Real ``energy_mean`` always
    # falls in (0, 1) for techno, so the filter was a no-op — the
    # ``up`` / ``down`` knob did nothing. Fix: compare candidate
    # against the SOURCE track's energy_mean. "up" => candidate hotter
    # than source; "down" => candidate cooler.
    if direction in {"up", "down"}:
        feat_ids = [*feat_ids, track_id]
    feat_map = await uow.track_features.get_scoring_features_batch(feat_ids)
    src_feat = feat_map.get(track_id) if direction in {"up", "down"} else None
    src_energy = src_feat.energy_mean if src_feat else None
    filtered_by_direction = 0
    for r in rows:
        feat_to = feat_map.get(r.to_track_id)
        if feat_to is None:
            continue
        cand_energy = feat_to.energy_mean
        # Need both energies to apply the directional filter; otherwise
        # we can't compare and the candidate falls through (we don't
        # silently drop it — log it via filtered_by_direction only when
        # the comparison was actually decisive).
        if (
            direction == "up"
            and cand_energy is not None
            and src_energy is not None
            and cand_energy <= src_energy
        ):
            filtered_by_direction += 1
            continue
        if (
            direction == "down"
            and cand_energy is not None
            and src_energy is not None
            and cand_energy >= src_energy
        ):
            filtered_by_direction += 1
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
    if not out and filtered_by_direction > 0:
        return [], f"all {filtered_by_direction} candidate(s) rejected by energy_direction filter"
    return out, None


async def _compute_suggest_replacement(
    uow: UnitOfWork,
    *,
    set_id: int,
    position: int,
    removed_track_id: int,
) -> tuple[list[dict[str, Any]], str | None]:
    """Candidate replacements: tracks with similar BPM/energy to removed_track_id,
    excluding tracks already in the set's latest version.

    Returns ``(candidates, reason)`` — empty ``candidates`` carries a
    short cause string so consumers can distinguish "set has no version
    yet", "removed track has no features", and "nothing within BPM
    window".
    """
    latest_version = getattr(uow.set_versions, "latest_version", None)
    if latest_version is None:
        return [], "set_versions repository does not expose latest_version yet"
    ver = await latest_version(set_id)
    if ver is None:
        return [], "set has no versions yet"
    items = await uow.set_versions.get_items(ver.id)
    excluded = {it.track_id for it in items}
    target_map = await uow.track_features.get_scoring_features_batch([removed_track_id])
    target_feat = target_map.get(removed_track_id)
    if target_feat is None:
        return [], f"track {removed_track_id} has no scoring features"
    bpm = target_feat.bpm or 0.0
    search_by_bpm_range = getattr(uow.tracks, "search_by_bpm_range", None)
    if search_by_bpm_range is None:
        return [], "tracks repository does not expose search_by_bpm_range yet"
    candidates = await search_by_bpm_range(
        bpm_min=bpm - 2.0, bpm_max=bpm + 2.0, exclude_ids=excluded, limit=10
    )
    if not candidates:
        return [], f"no library tracks within ±2 BPM of {bpm:.1f}"

    # Audit iter 42 (T-40): score each candidate against the surrounding
    # set track instead of returning a hardcoded ``score=0.0``. The
    # candidate slots in at ``position``; the natural anchor is the
    # track BEFORE it (the candidate would mix INTO that track). If
    # ``position`` is 0 (first slot, no predecessor), fall back to the
    # NEXT track (the candidate would mix OUT of). If neither exists
    # (single-track set), score=0.0 is honest.
    from app.domain.transition.scorer import TransitionScorer

    items_by_index = {item.sort_index: item for item in items}
    anchor_track_id: int | None = None
    anchor_role: str = "none"
    # ``position`` semantics: 0-based slot in items list. ``position-1``
    # = predecessor, ``position+1`` = successor (since the candidate
    # replaces the slot at ``position`` itself).
    if (position - 1) in items_by_index:
        anchor_track_id = items_by_index[position - 1].track_id
        anchor_role = "in"  # candidate mixes INTO anchor
    elif (position + 1) in items_by_index:
        anchor_track_id = items_by_index[position + 1].track_id
        anchor_role = "out"  # candidate mixes OUT to anchor

    candidate_ids = [t.id for t in candidates]
    feat_ids = candidate_ids + ([anchor_track_id] if anchor_track_id else [])
    feat_map = await uow.track_features.get_scoring_features_batch(feat_ids)
    anchor_feat = feat_map.get(anchor_track_id) if anchor_track_id else None

    scorer = TransitionScorer()
    out: list[dict[str, Any]] = []
    for t in candidates:
        cand_feat = feat_map.get(t.id)
        score: float = 0.0
        if anchor_feat is not None and cand_feat is not None:
            # Direction depends on whether the anchor is before or after
            # the candidate slot in the set.
            if anchor_role == "in":
                # candidate → anchor (candidate ends, anchor takes over)
                result = scorer.score(cand_feat, anchor_feat)
            else:
                # anchor → candidate (anchor ends, candidate takes over)
                result = scorer.score(anchor_feat, cand_feat)
            score = result.overall
        reason_parts = [f"bpm within 2 of {bpm}"]
        if anchor_track_id is None:
            reason_parts.append("no anchor — score is 0")
        elif cand_feat is None:
            reason_parts.append("candidate has no features — score is 0")
        out.append(
            {
                "track_id": t.id,
                "title": t.title,
                "score": score,
                "reason": "; ".join(reason_parts),
            }
        )
    # Best-quality-first.
    out.sort(key=lambda c: c["score"], reverse=True)
    return out, None
