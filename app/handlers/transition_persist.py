"""Handler for ``entity_create(entity="transition", data={from_track_id, to_track_id})``.

Loads scoring features for the pair, calls ``TransitionScorer``, picks a
Neural Mix preset via ``pick_neural_mix`` + ``build_recipe_for_pair``,
and persists the score *and* the materialised recipe into the
``transitions`` table (upsert on ``(from_track_id, to_track_id)``).
"""

from __future__ import annotations

from typing import Any, Protocol

from fastmcp.server.context import Context

from app.domain.transition.intent import TransitionIntent
from app.domain.transition.picker import build_recipe_for_pair
from app.domain.transition.recipe import NeuralMixRecipe
from app.domain.transition.score import TransitionScore
from app.domain.transition.section_context import SectionContext
from app.domain.transition.subgenre_rules import SubgenrePairType
from app.repositories.unit_of_work import UnitOfWork
from app.shared.errors import NotFoundError
from app.shared.features import TrackFeatures


class TransitionScorerProtocol(Protocol):
    def score(
        self,
        a: TrackFeatures,
        b: TrackFeatures,
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
    ) -> TransitionScore: ...


async def persist_transition_score(
    uow: UnitOfWork,
    *,
    from_track_id: int,
    to_track_id: int,
    score: TransitionScore,
    recipe: NeuralMixRecipe | None = None,
) -> Any:
    """Upsert a single ``TransitionScore`` (+ optional Neural Mix recipe) into ``transitions``.

    Single source of truth for the score → DB mapping. Both
    ``transition_persist_handler`` (single pair via ``entity_create``)
    and ``set_version_build_handler`` (every consecutive pair in a set)
    funnel through here so the column→field mapping stays consistent.

    Public TransitionScore field names are persisted into the v0
    ``harmonic_score`` / ``spectral_score`` / ``groove_score`` /
    ``timbral_score`` columns; internally these now hold the Neural Mix
    HARMONICS / BASS / DRUMS / VOCALS stem compatibilities (see
    ``app/domain/transition/score.py`` for the conceptual mapping).

    Returns the persisted row so callers can read its id / timestamps.
    """
    fields: dict[str, Any] = dict(
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
    if recipe is not None:
        fields["fx_type"] = str(recipe.transition)
        fields["transition_bars"] = int(recipe.bars)
        fields["transition_recipe_json"] = recipe.to_json()
    return await uow.transitions.upsert(
        from_track_id=from_track_id,
        to_track_id=to_track_id,
        **fields,
    )


def _build_recipe_or_none(
    score: TransitionScore,
    feat_a: TrackFeatures,
    feat_b: TrackFeatures,
    *,
    section_context: SectionContext | None = None,
    subgenre_pair: SubgenrePairType | None = None,
    intent: TransitionIntent | None = None,
) -> NeuralMixRecipe | None:
    """Materialise a Neural Mix recipe; swallow recipe-side errors so persist still lands."""
    try:
        return build_recipe_for_pair(
            score,
            feat_a,
            feat_b,
            section_context=section_context,
            subgenre_pair=subgenre_pair,
            intent=intent,
        )
    except Exception:
        return None


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

    feat_a = features[a_id]
    feat_b = features[b_id]
    score = scorer.score(feat_a, feat_b)
    recipe = _build_recipe_or_none(score, feat_a, feat_b)
    row = await persist_transition_score(
        uow,
        from_track_id=a_id,
        to_track_id=b_id,
        score=score,
        recipe=recipe,
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
        "transition": str(recipe.transition) if recipe is not None else None,
        "transition_bars": int(recipe.bars) if recipe is not None else None,
    }
