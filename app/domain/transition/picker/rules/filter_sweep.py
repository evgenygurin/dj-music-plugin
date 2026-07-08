from __future__ import annotations

from app.domain.transition.api import PickerRule
from app.domain.transition.enums import NeuralMixTransition, SubgenrePairType, TransitionIntent
from app.domain.transition.picker.api import PickerDecision
from app.domain.transition.score import TransitionScore
from app.domain.transition.section_context import SectionContext
from app.shared.features import TrackFeatures


class FilterSweepRule(PickerRule):
    name = "filter_sweep"
    confidence = 0.85

    def evaluate(
        self, score, from_t, to_t, *,
        section_context=None, subgenre_pair=None, intent=None,
    ) -> PickerDecision | None:
        if subgenre_pair not in (SubgenrePairType.ACID_PAIR, SubgenrePairType.HYPNOTIC_PAIR):
            return None
        if section_context is not None and section_context.is_drum_only_pair:
            return None
        return PickerDecision(
            transition=NeuralMixTransition.FILTER_SWEEP,
            confidence=self.confidence,
            reason="acid/hypnotic pair — filter sweep signature transition",
        )
