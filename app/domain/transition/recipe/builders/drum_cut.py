from __future__ import annotations

from app.domain.transition.neural_mix import NeuralMixStem, NeuralMixTransition
from app.domain.transition.recipe import DEFAULT_TRANSITION_BARS, MuteFXEvent, StemKeyframe

from ..envelopes.kill_with_echo import _cut
from .base import BaseRecipeBuilder


class DrumCutRecipeBuilder(BaseRecipeBuilder):
    transition = NeuralMixTransition.DRUM_CUT

    def _build_a_envelope(self, bars: int) -> list[StemKeyframe]:
        kfs, _ = _cut(bars, NeuralMixStem.DRUMS, slam_back=True)
        return list(kfs)

    def _build_b_envelope(self, bars: int) -> list[StemKeyframe]:
        return []

    def build(self, bars: int) -> tuple[tuple[StemKeyframe, ...], tuple[MuteFXEvent, ...]]:
        bars = bars or DEFAULT_TRANSITION_BARS
        return _cut(bars, NeuralMixStem.DRUMS, slam_back=True)
