"""Handler for entity_create(entity="transition", data={from_track_id, to_track_id}).

Loads scoring features for the pair, calls TransitionScorer, persists the
resulting TransitionScore into the `transitions` table (upsert on
(from_track_id, to_track_id)).
"""

from __future__ import annotations

from typing import Any, Protocol

from fastmcp.server.context import Context

from app.repositories.unit_of_work import UnitOfWork
from app.shared.errors import NotFoundError


class TransitionScorerProtocol(Protocol):
    def score(self, a: Any, b: Any, *, intent: Any = None, section_context: Any = None) -> Any: ...


async def transition_persist_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    scorer: TransitionScorerProtocol,
) -> dict[str, Any]:
    a_id: int = int(data["from_track_id"])
    b_id: int = int(data["to_track_id"])

    features = await uow.track_features.get_scoring_features_batch([a_id, b_id])
    if a_id not in features:
        raise NotFoundError("track_features", a_id)
    if b_id not in features:
        raise NotFoundError("track_features", b_id)

    score = scorer.score(features[a_id], features[b_id])
    row = await uow.transitions.upsert(
        from_track_id=a_id,
        to_track_id=b_id,
        bpm_score=float(score.bpm),
        harmonic_score=float(score.harmonic),
        energy_score=float(score.energy),
        spectral_score=float(score.spectral),
        groove_score=float(score.groove),
        timbral_score=float(score.timbral),
        overall_quality=float(score.overall),
        hard_reject=bool(score.hard_reject),
        reject_reason=score.reject_reason,
    )
    return {
        "id": row.id,
        "from_track_id": a_id,
        "to_track_id": b_id,
        "overall": float(score.overall),
        "bpm": float(score.bpm),
        "harmonic": float(score.harmonic),
        "energy": float(score.energy),
        "spectral": float(score.spectral),
        "groove": float(score.groove),
        "timbral": float(score.timbral),
        "hard_reject": bool(score.hard_reject),
        "reject_reason": score.reject_reason,
    }
