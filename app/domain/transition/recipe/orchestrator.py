from __future__ import annotations

from app.domain.transition.intent import TransitionIntent
from app.domain.transition.picker.pipeline import pick_neural_mix
from app.domain.transition.recipe import DEFAULT_TRANSITION_BARS, NeuralMixRecipe
from app.domain.transition.recipe.factory import build_recipe
from app.domain.transition.score import TransitionScore
from app.domain.transition.section_context import SectionContext
from app.domain.transition.subgenre_rules import SubgenrePairType, clamp_bars
from app.shared.features import TrackFeatures


def build_recipe_for_pair(
    score: TransitionScore,
    from_t: TrackFeatures,
    to_t: TrackFeatures,
    *,
    section_context: SectionContext | None = None,
    subgenre_pair: SubgenrePairType | None = None,
    intent: TransitionIntent | None = None,
    bars: int = DEFAULT_TRANSITION_BARS,
) -> NeuralMixRecipe:
    decision = pick_neural_mix(
        score,
        from_t,
        to_t,
        section_context=section_context,
        subgenre_pair=subgenre_pair,
        intent=intent,
    )
    effective_bars = clamp_bars(bars, subgenre_pair) if subgenre_pair is not None else bars
    return build_recipe(
        decision.transition,
        bars=effective_bars,
        mix_in_section=(
            section_context.to_section.name.lower()
            if section_context is not None and section_context.to_section is not None
            else None
        ),
        mix_out_section=(
            section_context.from_section.name.lower()
            if section_context is not None and section_context.from_section is not None
            else None
        ),
        confidence=decision.confidence,
        rescue=decision.rescue,
        explanation=decision.reason,
        warnings=decision.warnings,
    )
