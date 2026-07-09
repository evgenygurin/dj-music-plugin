from __future__ import annotations

from app.domain.transition.neural_mix import NeuralMixStem, NeuralMixTransition
from app.domain.transition.recipe import (
    DEFAULT_TRANSITION_BARS,
    LEVEL_SILENT,
    LEVEL_UNITY,
    MuteFXEvent,
    StemKeyframe,
)

from ..envelopes.linear_fade import _hold, _ramp
from .base import BaseRecipeBuilder


class FilterSweepRecipeBuilder(BaseRecipeBuilder):
    transition = NeuralMixTransition.FILTER_SWEEP

    def _build_a_envelope(self, bars: int) -> list[StemKeyframe]:
        b = float(bars)
        kfs: list[StemKeyframe] = []
        for stem in (
            NeuralMixStem.DRUMS,
            NeuralMixStem.BASS,
            NeuralMixStem.HARMONICS,
            NeuralMixStem.VOCALS,
        ):
            kfs.append(_hold("A", stem, LEVEL_UNITY, 0))
            kfs.extend(_ramp("A", stem, 4, b, LEVEL_UNITY, LEVEL_SILENT))
        return kfs

    def _build_b_envelope(self, bars: int) -> list[StemKeyframe]:
        b = float(bars)
        kfs: list[StemKeyframe] = []
        for stem in (
            NeuralMixStem.DRUMS,
            NeuralMixStem.BASS,
            NeuralMixStem.HARMONICS,
            NeuralMixStem.VOCALS,
        ):
            kfs.append(_hold("B", stem, LEVEL_SILENT, 0))
            kfs.extend(_ramp("B", stem, 4, b, LEVEL_SILENT, LEVEL_UNITY))
        return kfs

    def build(self, bars: int) -> tuple[tuple[StemKeyframe, ...], tuple[MuteFXEvent, ...]]:
        bars = bars or DEFAULT_TRANSITION_BARS
        a = self._build_a_envelope(bars)
        b = self._build_b_envelope(bars)
        return tuple(a + b), ()
