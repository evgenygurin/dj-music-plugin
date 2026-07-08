from __future__ import annotations

from app.domain.transition.neural_mix import NeuralMixStem, NeuralMixTransition
from app.domain.transition.recipe import DEFAULT_TRANSITION_BARS, MuteFXEvent, StemKeyframe

from ..envelopes.hold_then_fade import _sustain
from .base import BaseRecipeBuilder


class VocalSustainRecipeBuilder(BaseRecipeBuilder):
    transition = NeuralMixTransition.VOCAL_SUSTAIN

    def _build_a_envelope(self, bars: int) -> list[StemKeyframe]:
        return list(_sustain(bars, NeuralMixStem.VOCALS))

    def _build_b_envelope(self, bars: int) -> list[StemKeyframe]:
        return []

    def build(self, bars: int) -> tuple[tuple[StemKeyframe, ...], tuple[MuteFXEvent, ...]]:
        bars = bars or DEFAULT_TRANSITION_BARS
        return _sustain(bars, NeuralMixStem.VOCALS), ()
