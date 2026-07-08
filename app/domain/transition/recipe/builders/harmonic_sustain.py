from __future__ import annotations

from app.domain.transition.neural_mix import NeuralMixStem, NeuralMixTransition
from app.domain.transition.recipe import DEFAULT_TRANSITION_BARS, StemKeyframe

from ..envelopes.hold_then_fade import _sustain
from .base import BaseRecipeBuilder


class HarmonicSustainRecipeBuilder(BaseRecipeBuilder):
    transition = NeuralMixTransition.HARMONIC_SUSTAIN

    def _build_a_envelope(self, bars: int) -> list[StemKeyframe]:
        return list(_sustain(bars, NeuralMixStem.HARMONICS))

    def _build_b_envelope(self, bars: int) -> list[StemKeyframe]:
        return []

    def build(self, bars: int) -> tuple[tuple[StemKeyframe, ...], tuple]:
        bars = bars or DEFAULT_TRANSITION_BARS
        return _sustain(bars, NeuralMixStem.HARMONICS), ()
