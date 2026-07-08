from __future__ import annotations

from app.domain.transition.api import PickerRule
from app.domain.transition.enums import NeuralMixTransition, SubgenrePairType, TransitionIntent
from app.domain.transition.picker.api import PickerDecision


class AmbientOrCooldownRule(PickerRule):
    name = "ambient_or_cooldown"
    confidence = 0.78

    def evaluate(
        self,
        score,
        from_t,
        to_t,
        *,
        section_context=None,
        subgenre_pair=None,
        intent=None,
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
