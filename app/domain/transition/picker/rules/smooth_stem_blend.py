from __future__ import annotations

from app.domain.transition.api import PickerRule
from app.domain.transition.picker.api import PickerDecision


class SmoothStemBlendRule(PickerRule):
    name = "smooth_stem_blend"
    confidence = 0.75

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
        return None
