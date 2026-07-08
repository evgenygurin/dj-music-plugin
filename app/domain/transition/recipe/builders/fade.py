from __future__ import annotations

from app.domain.transition.neural_mix import NeuralMixTransition
from app.domain.transition.recipe import DEFAULT_TRANSITION_BARS, StemKeyframe

from ..envelopes.linear_fade import _crossfade_full
from .base import BaseRecipeBuilder


class FadeRecipeBuilder(BaseRecipeBuilder):
    transition = NeuralMixTransition.FADE

    def _build_a_envelope(self, bars: int) -> list[StemKeyframe]:
        return list(_crossfade_full("A", fade_in=False, bars=bars))

    def _build_b_envelope(self, bars: int) -> list[StemKeyframe]:
        return list(_crossfade_full("B", fade_in=True, bars=bars))

    def build(self, bars: int) -> tuple[tuple[StemKeyframe, ...], tuple]:
        bars = bars or DEFAULT_TRANSITION_BARS
        keyframes = self._build_a_envelope(bars) + self._build_b_envelope(bars)
        return tuple(keyframes), ()
