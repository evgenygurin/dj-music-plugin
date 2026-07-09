from __future__ import annotations

from app.domain.transition.neural_mix import NeuralMixStem
from app.domain.transition.recipe import LEVEL_SILENT, LEVEL_UNITY, Deck, StemKeyframe


def _hold(deck: Deck, stem: NeuralMixStem, level: float, bar: float) -> StemKeyframe:
    return StemKeyframe(bar=bar, deck=deck, stem=stem, level_db=level)


def _ramp(
    deck: Deck,
    stem: NeuralMixStem,
    start_bar: float,
    end_bar: float,
    start_level: float,
    end_level: float,
) -> tuple[StemKeyframe, StemKeyframe]:
    return (
        StemKeyframe(bar=start_bar, deck=deck, stem=stem, level_db=start_level),
        StemKeyframe(bar=end_bar, deck=deck, stem=stem, level_db=end_level),
    )


def _crossfade_full(deck: Deck, *, fade_in: bool, bars: int) -> tuple[StemKeyframe, ...]:
    start = LEVEL_SILENT if fade_in else LEVEL_UNITY
    end = LEVEL_UNITY if fade_in else LEVEL_SILENT
    out: list[StemKeyframe] = []
    for stem in NeuralMixStem:
        out.extend(_ramp(deck, stem, 0.0, float(bars), start, end))
    return tuple(out)
