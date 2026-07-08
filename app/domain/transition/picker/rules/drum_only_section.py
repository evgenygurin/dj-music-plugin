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

_DRUM_ONLY_DRUMS_HIGH = 0.85
_DRUM_ONLY_DRUMS_MID = 0.65


class DrumOnlySectionRule(PickerRule):
    name = "drum_only_section"
    confidence = 0.92

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
        if section_context is None or not section_context.is_drum_only_pair:
            return None
        if score.drums > _DRUM_ONLY_DRUMS_HIGH:
            return PickerDecision(
                transition=NeuralMixTransition.DRUM_SWAP,
                confidence=0.92,
                reason=f"drum-only sections, drums={score.drums:.2f} — swap drum bed",
            )
        if score.drums > _DRUM_ONLY_DRUMS_MID:
            return PickerDecision(
                transition=NeuralMixTransition.DRUM_CUT,
                confidence=0.85,
                reason=f"drum-only sections, drums={score.drums:.2f} — drumless reset",
            )
        return PickerDecision(
            transition=NeuralMixTransition.FADE,
            confidence=0.70,
            reason=f"drum-only sections, drums={score.drums:.2f} too low — linear fade",
        )
