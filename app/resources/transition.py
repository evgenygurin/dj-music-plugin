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
    # Audit iter 57 (T-55): same-track requests on the score / explain
    # resources used to return a synthetic 0.93 self-similarity row,
    # mirroring the now-fixed entity_create(transition) hole (T-52).
    # Reject up front so /score and /explain stay consistent with the
    # write paths.
    from app.shared.errors import ValidationError

    if from_id == to_id:
        raise ValidationError(
            f"transition score is undefined for a track against itself; "
            f"from_track_id and to_track_id must differ (got {from_id} for both)"
        )
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
    """Compute the live transition score for a pair.

    Always recomputes via the pure-domain ``TransitionScorer``. We
    deliberately ignore the ``transitions`` table here: rows there are
    written by ``set_version_build`` against features at the
    analysis-level current at build time, and have no cascade
    invalidation when ``track_features_reanalyze_handler`` raises a
    track to a higher level — so persisted rows can disagree with the
    live values (audit 2026-04-27, Bug C). ``TransitionScorer.score``
    is pure compute (≈1 ms/pair), the cache hit isn't worth the
    correctness risk, and ``/score`` and ``/explain`` now agree by
    construction. The ``transitions`` table remains write-only for
    set composition history.
    """
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
            "harmonics": score.harmonics,
            "energy": score.energy,
            "bass": score.bass,
            "drums": score.drums,
            "vocals": score.vocals,
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
        f"Harmonic component {score.harmonics:.2f}.",
        f"Energy component {score.energy:.2f}.",
    ]
    suggestions: list[str] = []
    if score.hard_reject:
        suggestions.append("hard reject — consider a bridge track")
    if score.harmonics < 0.55:
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
