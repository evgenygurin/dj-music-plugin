from __future__ import annotations

from app.domain.transition.api import PickerRule
from app.domain.transition.picker.api import PickerDecision


class HarmonicContinuityRule(PickerRule):
    name = "harmonic_continuity"
    confidence = 0.70

    def evaluate(
        self, score, from_t, to_t, *,
        section_context=None, subgenre_pair=None, intent=None,
    ) -> PickerDecision | None:
        return None
