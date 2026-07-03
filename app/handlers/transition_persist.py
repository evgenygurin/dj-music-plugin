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

from app.domain.transition.section_context import SectionContext, build_pair_context
from app.repositories.unit_of_work import UnitOfWork
from app.shared.constants import SectionType
from app.shared.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    from app.domain.transition.intent import TransitionIntent
    from app.domain.transition.recipe import NeuralMixRecipe
    from app.domain.transition.score import TransitionScore
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


def build_runtime_pair_context(
    outgoing: TrackFeatures,
    incoming: TrackFeatures,
    *,
    position: float,
    template: Any | None = None,
) -> Any:
    """Build pair context behind the handler/domain dependency boundary."""
    return build_pair_context(
        outgoing,
        incoming,
        position=position,
        template=template,
    )


async def persist_transition_score(
    uow: UnitOfWork,
    *,
    from_track_id: int,
    to_track_id: int,
    score: TransitionScore,
    recipe: NeuralMixRecipe | None = None,
    from_section_id: int | None = None,
    to_section_id: int | None = None,
    overlap_ms: int | None = None,
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
    if from_section_id is not None:
        fields["from_section_id"] = from_section_id
    if to_section_id is not None:
        fields["to_section_id"] = to_section_id
    if overlap_ms is not None:
        fields["overlap_ms"] = overlap_ms
    return await uow.transitions.upsert(
        from_track_id=from_track_id,
        to_track_id=to_track_id,
        **fields,
    )


def _resolve_section_context(payload: object) -> SectionContext | None:
    """Convert a ``section_context`` dict from ``TransitionCreate`` into
    a ``SectionContext`` instance, or return ``None`` if absent.

    Accepts ``SectionType`` values as either enum name (``"OUTRO"``)
    or integer value (``7``). Empty dict, missing keys, and unknown
    string aliases are treated as ``None`` for that side — the scorer
    then falls back to ``SectionPairClass.GENERIC`` (no overlay).
    """
    if payload is None:
        return None
    if not isinstance(payload, dict):
        return None

    def _coerce(val: object) -> SectionType | None:
        if val is None:
            return None
        if isinstance(val, SectionType):
            return val
        if isinstance(val, int):
            try:
                return SectionType(val)
            except ValueError:
                return None
        if isinstance(val, str):
            try:
                return SectionType[val.upper()]
            except KeyError:
                # Fall back to numeric string ("7" → SectionType(7))
                try:
                    return SectionType(int(val))
                except (ValueError, KeyError):
                    return None
        return None

    from_sec = _coerce(payload.get("from_section"))
    to_sec = _coerce(payload.get("to_section"))
    if from_sec is None and to_sec is None:
        return None
    return SectionContext(from_section=from_sec, to_section=to_sec)


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
        from app.domain.transition.subgenre_rules import classify_pair

        # Derive the subgenre pair from the tracks' moods when the caller
        # didn't supply one. Without this the picker's HARD/HYPNOTIC/ACID
        # branches (and the per-pair bar clamps) are dead on the set-build
        # path — which is why every persisted transition used to default
        # to ECHO_OUT. moods are L2 features, so this works on any analyzed
        # pair; classify_pair returns MIXED_PAIR for missing/unknown moods.
        if subgenre_pair is None:
            subgenre_pair = classify_pair(
                getattr(feat_a, "mood", None), getattr(feat_b, "mood", None)
            )

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

    # Phase 1 Task D: wire section_context from TransitionCreate through
    # to the scorer (applies the per-pair-class overlay) and to the
    # recipe builder (picker uses it to bias preset selection).
    section_context = _resolve_section_context(data.get("section_context"))

    score = scorer.score(feat_a, feat_b, section_context=section_context)
    recipe = _build_recipe_or_none(score, feat_a, feat_b, section_context=section_context)

    # Honour ``persist=False`` from ``TransitionCreate`` — the schema's
    # default is ``True`` but a caller asking ``persist=False`` wants the
    # score computed and returned without touching the ``transitions``
    # table. Previously the field was advertised on the schema but the
    # handler always wrote — same dead-parameter shape as
    # ``scoring_profile``. The compute path is identical; only the
    # ``upsert`` is conditional.
    persist_flag = data.get("persist", True)
    if persist_flag:
        row = await persist_transition_score(
            uow,
            from_track_id=a_id,
            to_track_id=b_id,
            score=score,
            recipe=recipe,
        )
        row_id: int | None = row.id
    else:
        row_id = None

    return {
        "id": row_id,
        "from_track_id": a_id,
        "to_track_id": b_id,
        "persisted": bool(persist_flag),
        "overall": float(score.overall),
        "bpm": float(score.bpm),
        "energy": float(score.energy),
        "drums": float(score.drums),
        "bass": float(score.bass),
        "harmonics": float(score.harmonics),
        "vocals": float(score.vocals),
        "section_pair_class": score.section_pair_class,
        "hard_reject": bool(score.hard_reject),
        "reject_reason": score.reject_reason,
        "transition": str(recipe.transition) if recipe is not None else None,
        "transition_bars": int(recipe.bars) if recipe is not None else None,
    }
