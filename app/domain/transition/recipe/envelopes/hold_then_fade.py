from __future__ import annotations

from app.domain.transition.neural_mix import NeuralMixStem
from app.domain.transition.recipe import LEVEL_SILENT, LEVEL_UNITY, Deck, StemKeyframe

from .linear_fade import _hold


def _sustain(
    bars: int,
    sustained_stem: NeuralMixStem,
) -> tuple[StemKeyframe, ...]:
    b = float(bars)
    quarter = b * 0.25
    three_q = b * 0.75
    seven_eighths = b * 0.875
    kfs: list[StemKeyframe] = []

    other_stems = tuple(s for s in NeuralMixStem if s is not sustained_stem)

    kfs += [
        _hold("A", sustained_stem, LEVEL_UNITY, 0.0),
        _hold("A", sustained_stem, LEVEL_UNITY, three_q),
        _hold("A", sustained_stem, LEVEL_SILENT, b),
    ]
    for stem in other_stems:
        kfs += [
            _hold("A", stem, LEVEL_UNITY, 0.0),
            _hold("A", stem, LEVEL_UNITY, quarter),
            _hold("A", stem, LEVEL_SILENT, three_q),
        ]
    for stem in other_stems:
        kfs += [
            _hold("B", stem, LEVEL_SILENT, 0.0),
            _hold("B", stem, LEVEL_SILENT, quarter),
            _hold("B", stem, LEVEL_UNITY, three_q),
        ]
    kfs += [
        _hold("B", sustained_stem, LEVEL_SILENT, 0.0),
        _hold("B", sustained_stem, LEVEL_SILENT, seven_eighths),
        _hold("B", sustained_stem, LEVEL_UNITY, b),
    ]
    return tuple(kfs)
