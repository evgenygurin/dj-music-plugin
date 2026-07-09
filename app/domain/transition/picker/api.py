from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.transition.neural_mix import NeuralMixTransition


@dataclass(frozen=True)
class PickerDecision:
    """Output of ``pick_neural_mix``: which preset, why, and the rescue fallback."""

    transition: NeuralMixTransition
    confidence: float
    reason: str
    warnings: tuple[str, ...] = field(default_factory=tuple)
    rescue: NeuralMixTransition = NeuralMixTransition.ECHO_OUT
