from __future__ import annotations

from app.domain.transition.api import PickerRule
from app.domain.transition.enums import NeuralMixTransition
from app.domain.transition.picker.api import PickerDecision
from app.domain.transition.picker.proxies.vocal_activity import (
    _vocal_active,
    _vocal_data_missing,
    _vocal_low,
)


class VocalActiveRule(PickerRule):
    name = "vocal_active"
    confidence = 0.88

    def evaluate(
        self, score, from_t, to_t, *,
        section_context=None, subgenre_pair=None, intent=None,
    ) -> PickerDecision | None:
        if not _vocal_active(from_t):
            return None
        if _vocal_data_missing(to_t):
            return PickerDecision(
                transition=NeuralMixTransition.ECHO_OUT,
                confidence=0.65,
                reason="A vocal-active, B vocal data missing — echo-tail safe default",
                warnings=("incoming track missing vocal-presence proxy features",),
            )
        if _vocal_low(to_t):
            return PickerDecision(
                transition=NeuralMixTransition.VOCAL_SUSTAIN,
                confidence=0.88,
                reason="A vocal-active, B vocal-light — sustain A vocal over B inst",
            )
        return PickerDecision(
            transition=NeuralMixTransition.VOCAL_CUT,
            confidence=0.82,
            reason="A and B both vocal-active — cut A vocal to avoid clash",
            warnings=("two vocal lines — cut prevents stacking but timing must land",),
        )
