from __future__ import annotations

from app.domain.transition.api import PickerRule
from app.domain.transition.enums import NeuralMixTransition, SubgenrePairType, TransitionIntent
from app.domain.transition.picker.api import PickerDecision
from app.domain.transition.picker.proxies.camelot_compatibility import _energy_delta_lufs

_ENERGY_DELTA_RAMP_UP_LUFS = 2.0


class EnergyDropToSlamRule(PickerRule):
    name = "energy_drop_to_slam"
    confidence = 0.86

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
        delta = _energy_delta_lufs(from_t, to_t)
        if delta is None or delta <= _ENERGY_DELTA_RAMP_UP_LUFS:
            return None
        if not (intent is TransitionIntent.RAMP_UP or subgenre_pair is SubgenrePairType.HARD_PAIR):
            return None
        return PickerDecision(
            transition=NeuralMixTransition.DRUM_CUT,
            confidence=self.confidence,
            reason=f"energy delta +{delta:.1f} LUFS into ramp-up — breakdown + slam",
        )
