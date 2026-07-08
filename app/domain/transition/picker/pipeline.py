from __future__ import annotations

from app.domain.transition.api import PickerRule
from app.domain.transition.enums import NeuralMixTransition, SubgenrePairType, TransitionIntent
from app.domain.transition.picker.api import PickerDecision
from app.domain.transition.picker.rules import DEFAULT_RULES
from app.domain.transition.score import TransitionScore
from app.domain.transition.section_context import SectionContext
from app.shared.features import TrackFeatures


class PickerPipeline:
    def __init__(self, rules: tuple[PickerRule, ...] | None = None) -> None:
        self._rules = rules or DEFAULT_RULES

    def pick(
        self,
        score: TransitionScore,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        section_context: SectionContext | None = None,
        subgenre_pair: SubgenrePairType | None = None,
        intent: TransitionIntent | None = None,
    ) -> PickerDecision:
        for rule in self._rules:
            decision = rule.evaluate(
                score,
                from_t,
                to_t,
                section_context=section_context,
                subgenre_pair=subgenre_pair,
                intent=intent,
            )
            if decision is not None:
                return decision
        return PickerDecision(
            transition=NeuralMixTransition.ECHO_OUT,
            confidence=0.50,
            reason="no rule matched — default echo out",
        )


def pick_neural_mix(
    score, from_t, to_t, *, section_context=None, subgenre_pair=None, intent=None
) -> PickerDecision:
    pipeline = PickerPipeline()
    return pipeline.pick(
        score,
        from_t,
        to_t,
        section_context=section_context,
        subgenre_pair=subgenre_pair,
        intent=intent,
    )
