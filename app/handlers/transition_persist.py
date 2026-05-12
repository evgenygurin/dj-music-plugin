"""Handler for ``entity_create(entity="transition", data={from_track_id, to_track_id})``.

Loads scoring features for the pair, calls ``TransitionScorer``, picks a
Neural Mix preset via ``pick_neural_mix`` + ``build_recipe_for_pair``,
and persists the score *and* the materialised recipe into the
``transitions`` table (upsert on ``(from_track_id, to_track_id)``).

Domain-side imports are deliberately lazy inside function bodies —
``app.handlers.transition_persist`` is reached transitively from
``app.server.lifespan`` via ``app.registry.defaults``, and the
``v2-server-no-domain`` import-linter contract forbids the server
package from statically pulling ``app.domain``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from fastmcp.server.context import Context

from app.repositories.unit_of_work import UnitOfWork
from app.shared.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    from app.domain.transition.intent import TransitionIntent
    from app.domain.transition.recipe import NeuralMixRecipe
    from app.domain.transition.score import TransitionScore
    from app.domain.transition.section_context import SectionContext
    from app.domain.transition.subgenre_rules import SubgenrePairType
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
    """Upsert a single ``TransitionScore`` (+ optional Neural Mix recipe).

    Single source of truth for the score → DB mapping. Both
    ``transition_persist_handler`` (single pair via ``entity_create``)
    and ``set_version_build_handler`` (every consecutive pair in a set)
    funnel through here so the column→field mapping stays consistent.

    Public TransitionScore field names are persisted into the v0
    ``drums_score`` / ``bass_score`` / ``harmonics_score`` /
    ``vocals_score`` columns, holding Neural Mix
    HARMONICS / BASS / DRUMS / VOCALS stem compatibilities.
    """
    fields: dict[str, Any] = dict(
        bpm_score=float(score.bpm),
        energy_score=float(score.energy),
        drums_score=float(score.drums),
        bass_score=float(score.bass),
        harmonics_score=float(score.harmonics),
        vocals_score=float(score.vocals),
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
        # Lazy import — keeps app.server transitively clean of app.domain
        # per the v2-server-no-domain import-linter contract.
        from app.domain.transition.picker import build_recipe_for_pair

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

    # ``TransitionCreate.scoring_profile`` is exposed in the schema as
    # "use this named profile's weights" but the handler currently
    # ignores it — a typo (``scoring_profile="bogus"``) used to silently
    # fall through to the default weights. At minimum validate the
    # profile exists so the caller's intent isn't dropped without a
    # signal. Wiring the weights into a custom ``TransitionScorer``
    # is future work.
    profile_name = data.get("scoring_profile")
    if profile_name:
        profile = await uow.scoring_profiles.get_by_name(str(profile_name))
        if profile is None:
            raise ValidationError(
                f"scoring_profile {profile_name!r} not found; "
                f"create it via entity_create(scoring_profile, ...) first, "
                f"or omit the field to use the default weights",
                details={"scoring_profile": profile_name},
            )

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
        "energy": float(score.energy),
        "drums": float(score.drums),
        "bass": float(score.bass),
        "harmonics": float(score.harmonics),
        "vocals": float(score.vocals),
        "hard_reject": bool(score.hard_reject),
        "reject_reason": score.reject_reason,
        "transition": str(recipe.transition) if recipe is not None else None,
        "transition_bars": int(recipe.bars) if recipe is not None else None,
    }
