from __future__ import annotations

from app.domain.transition.neural_mix import NeuralMixTransition
from app.domain.transition.recipe import DEFAULT_TRANSITION_BARS, StemKeyframe

from ..envelopes.enter_ramp import _drum_swap_envelope
from .base import BaseRecipeBuilder


class DrumSwapRecipeBuilder(BaseRecipeBuilder):
    transition = NeuralMixTransition.DRUM_SWAP

    def _build_a_envelope(self, bars: int) -> list[StemKeyframe]:
        return list(_drum_swap_envelope(bars))

    def _build_b_envelope(self, bars: int) -> list[StemKeyframe]:
        return []

    def build(self, bars: int) -> tuple[tuple[StemKeyframe, ...], tuple]:
        bars = bars or DEFAULT_TRANSITION_BARS
        return _drum_swap_envelope(bars), ()
