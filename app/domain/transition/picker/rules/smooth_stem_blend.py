from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.transition.api import PickerRule
from app.domain.transition.picker.api import PickerDecision

if TYPE_CHECKING:
    from app.domain.transition.enums import SubgenrePairType, TransitionIntent
    from app.domain.transition.score import TransitionScore
    from app.domain.transition.section_context import SectionContext
    from app.shared.features import TrackFeatures


class SmoothStemBlendRule(PickerRule):
    name = "smooth_stem_blend"
    confidence = 0.75

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
        return None
