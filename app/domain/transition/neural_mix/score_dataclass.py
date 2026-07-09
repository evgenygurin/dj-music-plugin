from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.domain.transition.neural_mix.enums import NeuralMixStem, NeuralMixTransition

if TYPE_CHECKING:
    pass


@dataclass
class NeuralMixScore:
    stem_scores: dict[NeuralMixStem, float] = field(default_factory=dict)
    transition_scores: dict[NeuralMixTransition, float] = field(default_factory=dict)
    best_transition: NeuralMixTransition | None = None
    overall: float = 0.0
    hard_reject: bool = False
    reject_reason: str | None = None

    @property
    def drums_compat(self) -> float:
        return self.stem_scores.get(NeuralMixStem.DRUMS, 0.0)

    @property
    def bass_compat(self) -> float:
        return self.stem_scores.get(NeuralMixStem.BASS, 0.0)

    @property
    def harmonic_compat(self) -> float:
        return self.stem_scores.get(NeuralMixStem.HARMONICS, 0.0)

    @property
    def vocal_compat(self) -> float:
        return self.stem_scores.get(NeuralMixStem.VOCALS, 0.0)
