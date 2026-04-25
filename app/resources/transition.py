"""Pairwise transition resources.

URIs:
    local://transition/{from_id}/{to_id}/score
    local://transition/{from_id}/{to_id}/explain
"""

from __future__ import annotations

from fastmcp.dependencies import Depends
from fastmcp.resources import resource

from app.domain.transition.scorer import TransitionScorer
from app.repositories.unit_of_work import UnitOfWork
from app.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META
from app.schemas.resource_views import (
    TransitionExplainView,
    TransitionScoreView,
)
from app.server.di import get_uow
from app.shared.errors import NotFoundError
from app.shared.features import TrackFeatures


async def _load_features_pair(uow: UnitOfWork, from_id: int, to_id: int) -> tuple[object, object]:
    feats = await uow.track_features.get_scoring_features_batch([from_id, to_id])
    feat_a = feats.get(from_id)
    feat_b = feats.get(to_id)
    if feat_a is None or feat_b is None:
        raise NotFoundError("track_features", f"{from_id} or {to_id}")
    return feat_a, feat_b


@resource(
    "local://transition/{from_id}/{to_id}/score",
    mime_type="application/json",
    tags={"core", "namespace:reasoning", "view:transition_score"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def transition_score(
    from_id: int,
    to_id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Compute (or read persisted) transition score.

    Strategy: prefer persisted row via ``transitions.get_by_pair``; fall
    back to live scoring using the pure-domain ``TransitionScorer``.
    """
    get_by_pair = getattr(uow.transitions, "get_by_pair", None)
    persisted = await get_by_pair(from_id, to_id) if get_by_pair is not None else None
    if persisted is not None:
        return TransitionScoreView(
            from_track_id=from_id,
            to_track_id=to_id,
            overall=getattr(persisted, "overall_quality", 0.0) or 0.0,
            hard_reject=bool(getattr(persisted, "hard_reject", False)),
            reject_reason=getattr(persisted, "reject_reason", None),
            components={
                "bpm": getattr(persisted, "bpm_score", 0.0) or 0.0,
                "harmonic": getattr(persisted, "harmonic_score", 0.0) or 0.0,
                "energy": getattr(persisted, "energy_score", 0.0) or 0.0,
                "spectral": getattr(persisted, "spectral_score", 0.0) or 0.0,
                "groove": getattr(persisted, "groove_score", 0.0) or 0.0,
                "timbral": getattr(persisted, "timbral_score", 0.0) or 0.0,
            },
        ).model_dump_json()

    feat_a, feat_b = await _load_features_pair(uow, from_id, to_id)
    score = TransitionScorer().score(TrackFeatures.from_db(feat_a), TrackFeatures.from_db(feat_b))
    return TransitionScoreView(
        from_track_id=from_id,
        to_track_id=to_id,
        overall=score.overall,
        hard_reject=score.hard_reject,
        reject_reason=score.reject_reason,
        components={
            "bpm": score.bpm,
            "harmonic": score.harmonic,
            "energy": score.energy,
            "spectral": score.spectral,
            "groove": score.groove,
            "timbral": score.timbral,
        },
    ).model_dump_json()


@resource(
    "local://transition/{from_id}/{to_id}/explain",
    mime_type="application/json",
    tags={"core", "namespace:reasoning", "view:transition_explain"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def transition_explain(
    from_id: int,
    to_id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Narrative explanation of a pairwise transition."""
    feat_a, feat_b = await _load_features_pair(uow, from_id, to_id)
    score = TransitionScorer().score(TrackFeatures.from_db(feat_a), TrackFeatures.from_db(feat_b))
    bpm_a = getattr(feat_a, "bpm", None)
    bpm_b = getattr(feat_b, "bpm", None)
    parts: list[str] = [
        f"BPM: {bpm_a} -> {bpm_b} (component {score.bpm:.2f}).",
        f"Harmonic component {score.harmonic:.2f}.",
        f"Energy component {score.energy:.2f}.",
    ]
    suggestions: list[str] = []
    if score.hard_reject:
        suggestions.append("hard reject — consider a bridge track")
    if score.harmonic < 0.55:
        suggestions.append("long blend (32 bars) over key drift")
    if score.energy < 0.4:
        suggestions.append("echo-out to soften energy gap")
    return TransitionExplainView(
        from_track_id=from_id,
        to_track_id=to_id,
        overall=score.overall,
        narrative=" ".join(parts),
        suggestions=suggestions,
    ).model_dump_json()
