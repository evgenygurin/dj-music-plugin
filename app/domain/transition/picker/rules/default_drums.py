from __future__ import annotations

from app.domain.transition.api import PickerRule
from app.domain.transition.enums import NeuralMixTransition
from app.domain.transition.picker.api import PickerDecision
from app.domain.transition.picker.proxies.camelot_compatibility import _energy_delta_lufs

_DRUM_SWAP_FLOOR = 0.62
_DRUM_CUT_FLOOR = 0.45
_DRUM_CUT_ENERGY_LIFT_LUFS = 2.0


class DefaultDrumsRule(PickerRule):
    name = "default_drums"
    confidence = 0.82

    def evaluate(
        self, score, from_t, to_t, *,
        section_context=None, subgenre_pair=None, intent=None,
    ) -> PickerDecision | None:
        delta = _energy_delta_lufs(from_t, to_t)
        if score.drums >= _DRUM_SWAP_FLOOR:
            if delta is not None and delta > _DRUM_CUT_ENERGY_LIFT_LUFS:
                return PickerDecision(
                    transition=NeuralMixTransition.DRUM_CUT,
                    confidence=0.80,
                    reason=(
                        f"drums lock ({score.drums:.2f}), energy +{delta:.1f} LUFS — "
                        f"quick drum cut to lift"
                    ),
                )
            return PickerDecision(
                transition=NeuralMixTransition.DRUM_SWAP,
                confidence=self.confidence,
                reason=f"drum-driven techno, drums={score.drums:.2f} — long EQ-swap blend",
            )
        if score.drums >= _DRUM_CUT_FLOOR:
            return PickerDecision(
                transition=NeuralMixTransition.DRUM_CUT,
                confidence=0.72,
                reason=f"grooves loosely lock (drums={score.drums:.2f}) — quick drum cut",
            )
        return PickerDecision(
            transition=NeuralMixTransition.ECHO_OUT,
            confidence=0.60,
            reason=f"groove mismatch (drums={score.drums:.2f}) — echo-tail rescue",
        )
