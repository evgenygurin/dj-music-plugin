from __future__ import annotations

from app.domain.transition.neural_mix import NeuralMixStem, NeuralMixTransition
from app.domain.transition.recipe import (
    DEFAULT_TRANSITION_BARS,
    LEVEL_SILENT,
    LEVEL_UNITY,
    MuteFXEvent,
    MuteFXTrigger,
    StemKeyframe,
)

from ..envelopes.linear_fade import _hold
from .base import BaseRecipeBuilder


class EchoOutRecipeBuilder(BaseRecipeBuilder):
    transition = NeuralMixTransition.ECHO_OUT

    def _build_a_envelope(self, bars: int) -> list[StemKeyframe]:
        b = float(bars)
        quarter = b * 0.25
        half = b * 0.50
        three_q = b * 0.75
        return [
            _hold("A", NeuralMixStem.VOCALS, LEVEL_UNITY, 0.0),
            _hold("A", NeuralMixStem.VOCALS, LEVEL_UNITY, quarter - 0.01),
            _hold("A", NeuralMixStem.VOCALS, LEVEL_SILENT, quarter),
            _hold("A", NeuralMixStem.HARMONICS, LEVEL_UNITY, 0.0),
            _hold("A", NeuralMixStem.HARMONICS, LEVEL_UNITY, half - 0.01),
            _hold("A", NeuralMixStem.HARMONICS, LEVEL_SILENT, half),
            _hold("A", NeuralMixStem.DRUMS, LEVEL_UNITY, 0.0),
            _hold("A", NeuralMixStem.DRUMS, LEVEL_UNITY, three_q - 0.01),
            _hold("A", NeuralMixStem.DRUMS, LEVEL_SILENT, three_q),
            _hold("A", NeuralMixStem.BASS, LEVEL_UNITY, 0.0),
            _hold("A", NeuralMixStem.BASS, LEVEL_UNITY, three_q - 0.01),
            _hold("A", NeuralMixStem.BASS, LEVEL_SILENT, three_q),
        ]

    def _build_b_envelope(self, bars: int) -> list[StemKeyframe]:
        b = float(bars)
        half = b * 0.50
        three_q = b * 0.75
        seven_eighths = b * 0.875
        return [
            _hold("B", NeuralMixStem.DRUMS, LEVEL_SILENT, 0.0),
            _hold("B", NeuralMixStem.DRUMS, LEVEL_SILENT, half),
            _hold("B", NeuralMixStem.DRUMS, LEVEL_UNITY, three_q),
            _hold("B", NeuralMixStem.BASS, LEVEL_SILENT, 0.0),
            _hold("B", NeuralMixStem.BASS, LEVEL_SILENT, half),
            _hold("B", NeuralMixStem.BASS, LEVEL_UNITY, three_q),
            _hold("B", NeuralMixStem.HARMONICS, LEVEL_SILENT, 0.0),
            _hold("B", NeuralMixStem.HARMONICS, LEVEL_SILENT, b * 0.625),
            _hold("B", NeuralMixStem.HARMONICS, LEVEL_UNITY, seven_eighths),
            _hold("B", NeuralMixStem.VOCALS, LEVEL_SILENT, 0.0),
            _hold("B", NeuralMixStem.VOCALS, LEVEL_SILENT, seven_eighths),
            _hold("B", NeuralMixStem.VOCALS, LEVEL_UNITY, b),
        ]

    def _build_fx_events(self, bars: int) -> tuple[MuteFXEvent, ...]:
        b = float(bars)
        quarter = b * 0.25
        half = b * 0.50
        three_q = b * 0.75
        return (
            MuteFXEvent(
                bar=quarter, deck="A", stem=NeuralMixStem.VOCALS, trigger=MuteFXTrigger.ECHO_3_4
            ),
            MuteFXEvent(
                bar=half, deck="A", stem=NeuralMixStem.HARMONICS, trigger=MuteFXTrigger.ECHO_3_4
            ),
            MuteFXEvent(
                bar=three_q, deck="A", stem=NeuralMixStem.DRUMS, trigger=MuteFXTrigger.ECHO_3_4
            ),
            MuteFXEvent(
                bar=three_q, deck="A", stem=NeuralMixStem.BASS, trigger=MuteFXTrigger.ECHO_3_4
            ),
        )

    def build(self, bars: int) -> tuple[tuple[StemKeyframe, ...], tuple[MuteFXEvent, ...]]:
        bars = bars or DEFAULT_TRANSITION_BARS
        a = self._build_a_envelope(bars)
        b = self._build_b_envelope(bars)
        fx = self._build_fx_events(bars)
        return tuple(a + b), fx
