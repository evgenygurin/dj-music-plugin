from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.transition.neural_mix import NeuralMixTransition
from app.domain.transition.recipe import StemKeyframe


class BaseRecipeBuilder(ABC):
    transition: NeuralMixTransition

    @abstractmethod
    def _build_a_envelope(self, bars: int) -> list[StemKeyframe]: ...

    @abstractmethod
    def _build_b_envelope(self, bars: int) -> list[StemKeyframe]: ...

    def _build_fx_events(self, bars: int) -> tuple:
        return ()

    def build(self, bars: int) -> tuple[tuple[StemKeyframe, ...], tuple]:
        a = self._build_a_envelope(bars)
        b = self._build_b_envelope(bars)
        fx = self._build_fx_events(bars)
        return tuple(a + b), fx
