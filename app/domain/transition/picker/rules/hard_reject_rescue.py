from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.transition.api import PickerRule
from app.domain.transition.enums import NeuralMixTransition
from app.domain.transition.picker.api import PickerDecision

if TYPE_CHECKING:
    from app.domain.transition.enums import SubgenrePairType, TransitionIntent
    from app.domain.transition.score import TransitionScore
    from app.domain.transition.section_context import SectionContext
    from app.shared.features import TrackFeatures


class HardRejectRescueRule(PickerRule):
    name = "hard_reject_rescue"
    confidence = 0.55

    def evaluate(
        self,
        score: TransitionScore,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        section_context: SectionContext | None = None,
        subgenre_pair: SubgenrePairType | None = None,
        intent: TransitionIntent | None = None,
    ) -> PickerDecision | None:
        if not score.hard_reject:
            return None

        reason = score.reject_reason or ""

        if "camelot" in reason.lower() or "key" in reason.lower():
            return PickerDecision(
                transition=NeuralMixTransition.FILTER_SWEEP,
                confidence=0.55,
                reason=f"camelot clash rescue -> filter sweep ({reason})",
            )

        return PickerDecision(
            transition=NeuralMixTransition.ECHO_OUT,
            confidence=0.55,
            reason=f"hard reject rescue -> echo out ({reason})",
        )
