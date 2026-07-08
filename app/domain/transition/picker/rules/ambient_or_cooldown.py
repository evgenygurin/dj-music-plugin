from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.transition.api import PickerRule
from app.domain.transition.enums import NeuralMixTransition, SubgenrePairType, TransitionIntent
from app.domain.transition.picker.api import PickerDecision

if TYPE_CHECKING:
    from app.domain.transition.score import TransitionScore
    from app.domain.transition.section_context import SectionContext
    from app.shared.features import TrackFeatures


class AmbientOrCooldownRule(PickerRule):
    name = "ambient_or_cooldown"
    confidence = 0.78

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
        if subgenre_pair is SubgenrePairType.AMBIENT_PAIR:
            return PickerDecision(
                transition=NeuralMixTransition.FADE,
                confidence=self.confidence,
                reason="ambient pair / cool-down intent — linear stem crossfade",
            )
        if intent is TransitionIntent.COOL_DOWN:
            return PickerDecision(
                transition=NeuralMixTransition.FADE,
                confidence=self.confidence,
                reason="cool-down intent — linear stem crossfade",
            )
        return None
