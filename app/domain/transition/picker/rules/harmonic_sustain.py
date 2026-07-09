from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.transition.api import PickerRule
from app.domain.transition.enums import NeuralMixTransition
from app.domain.transition.picker.api import PickerDecision
from app.domain.transition.picker.proxies.camelot_compatibility import _camelot_compatible
from app.domain.transition.picker.proxies.harmonic_motif import _harmonic_motif
from app.domain.transition.picker.proxies.vocal_activity import _vocal_low

if TYPE_CHECKING:
    from app.domain.transition.enums import SubgenrePairType, TransitionIntent
    from app.domain.transition.score import TransitionScore
    from app.domain.transition.section_context import SectionContext
    from app.shared.features import TrackFeatures


class HarmonicSustainRule(PickerRule):
    name = "harmonic_sustain"
    confidence = 0.83

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
        if not _harmonic_motif(from_t):
            return None
        if not _camelot_compatible(from_t, to_t):
            return None
        if not _vocal_low(to_t):
            return None
        return PickerDecision(
            transition=NeuralMixTransition.HARMONIC_SUSTAIN,
            confidence=self.confidence,
            reason="A harmonic motif, key compatible, B vocal-light — sustain A harmonic",
        )
