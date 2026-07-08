from __future__ import annotations

from app.domain.transition.api import PickerRule
from app.domain.transition.enums import NeuralMixTransition, SubgenrePairType, TransitionIntent
from app.domain.transition.picker.api import PickerDecision
from app.domain.transition.score import TransitionScore
from app.domain.transition.section_context import SectionContext
from app.shared.features import TrackFeatures


class HardRejectRescueRule(PickerRule):
    name = "hard_reject_rescue"
    confidence = 0.55

    def evaluate(
        self, score, from_t, to_t, *,
        section_context=None, subgenre_pair=None, intent=None,
    ) -> PickerDecision | None:
        if not score.hard_reject:
            return None
        return PickerDecision(
            transition=NeuralMixTransition.ECHO_OUT,
            confidence=self.confidence,
            reason=f"hard reject ({score.reject_reason or 'unknown'}) — echo-tail rescue",
            warnings=("hard reject — recipe is best-effort",),
        )
