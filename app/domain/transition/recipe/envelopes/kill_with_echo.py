from __future__ import annotations

from app.domain.transition.neural_mix import NeuralMixStem
from app.domain.transition.recipe import MuteFXEvent, MuteFXTrigger


def _echo_trigger(bar: float, deck: str, stem: NeuralMixStem, trigger: MuteFXTrigger) -> MuteFXEvent:
    return MuteFXEvent(bar=bar, deck=deck, stem=stem, trigger=trigger)


def _cut(
    bars: int,
    cut_stem: NeuralMixStem,
    *,
    slam_back: bool,
) -> tuple[tuple[object, ...], tuple[MuteFXEvent, ...]]:
    from app.domain.transition.recipe import LEVEL_SILENT, LEVEL_UNITY

    from .linear_fade import _hold

    b = float(bars)
    eighth = b * 0.125
    seven_eighths = b * 0.875
    kfs: list = []

    kfs += [
        _hold("A", cut_stem, LEVEL_UNITY, 0.0),
        _hold("A", cut_stem, LEVEL_UNITY, max(0.0, b * 0.03125)),
        _hold("A", cut_stem, LEVEL_SILENT, eighth),
    ]
    other_stems = tuple(s for s in NeuralMixStem if s is not cut_stem)
    for stem in other_stems:
        kfs += [
            _hold("A", stem, LEVEL_UNITY, 0.0),
            _hold("A", stem, LEVEL_UNITY, eighth),
            _hold("A", stem, LEVEL_SILENT, seven_eighths),
        ]
    for stem in other_stems:
        kfs += [
            _hold("B", stem, LEVEL_SILENT, 0.0),
            _hold("B", stem, LEVEL_SILENT, eighth),
            _hold("B", stem, LEVEL_UNITY, seven_eighths),
        ]
    if slam_back:
        kfs += [
            _hold("B", cut_stem, LEVEL_SILENT, 0.0),
            _hold("B", cut_stem, LEVEL_SILENT, b - 0.5),
            _hold("B", cut_stem, LEVEL_UNITY, b),
        ]
    else:
        kfs += [
            _hold("B", cut_stem, LEVEL_SILENT, 0.0),
            _hold("B", cut_stem, LEVEL_SILENT, seven_eighths),
            _hold("B", cut_stem, LEVEL_UNITY, b),
        ]

    fx = (MuteFXEvent(bar=eighth, deck="A", stem=cut_stem, trigger=MuteFXTrigger.ECHO_1_2),)
    return tuple(kfs), fx
