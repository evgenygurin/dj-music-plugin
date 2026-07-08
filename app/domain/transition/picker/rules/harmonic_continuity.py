from __future__ import annotations

from app.domain.transition.api import PickerRule
from app.domain.transition.enums import NeuralMixTransition, SubgenrePairType, TransitionIntent
from app.domain.transition.picker.api import PickerDecision
from app.domain.transition.score import TransitionScore
from app.domain.transition.section_context import SectionContext
from app.shared.features import TrackFeatures


class HarmonicContinuityRule(PickerRule):
    name = "harmonic_continuity"
    confidence = 0.70

    def evaluate(
        self, score, from_t, to_t, *,
        section_context=None, subgenre_pair=None, intent=None,
    ) -> PickerDecision | None:
        return None
