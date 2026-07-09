from __future__ import annotations

from app.domain.transition.neural_mix import NeuralMixStem
from app.domain.transition.recipe import LEVEL_SILENT, LEVEL_UNITY, StemKeyframe

from .linear_fade import _hold


def _drum_swap_envelope(bars: int) -> tuple[StemKeyframe, ...]:
    b = float(bars)
    half = b * 0.5
    kfs: list[StemKeyframe] = []

    kfs += [
        _hold("A", NeuralMixStem.DRUMS, LEVEL_UNITY, 0.0),
        _hold("A", NeuralMixStem.DRUMS, LEVEL_SILENT, half),
        _hold("A", NeuralMixStem.DRUMS, LEVEL_SILENT, b),
        _hold("B", NeuralMixStem.DRUMS, LEVEL_SILENT, 0.0),
        _hold("B", NeuralMixStem.DRUMS, LEVEL_UNITY, half),
        _hold("B", NeuralMixStem.DRUMS, LEVEL_UNITY, b),
    ]
    for stem in (NeuralMixStem.BASS, NeuralMixStem.HARMONICS, NeuralMixStem.VOCALS):
        kfs += [
            _hold("A", stem, LEVEL_UNITY, 0.0),
            _hold("A", stem, LEVEL_UNITY, half),
            _hold("A", stem, LEVEL_SILENT, b),
            _hold("B", stem, LEVEL_SILENT, 0.0),
            _hold("B", stem, LEVEL_SILENT, half),
            _hold("B", stem, LEVEL_UNITY, b),
        ]
    return tuple(kfs)
