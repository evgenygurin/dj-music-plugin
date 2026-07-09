from app.domain.transition.neural_mix.data import (
    NEURAL_MIX_STEMS,
    TRANSITION_ENERGY_BIAS,
    TRANSITION_STEM_WEIGHTS,
    TRANSITION_TYPES,
)
from app.domain.transition.neural_mix.enums import NeuralMixStem, NeuralMixTransition
from app.domain.transition.neural_mix.score_dataclass import NeuralMixScore
from app.domain.transition.neural_mix.scorer import NeuralMixScorer

# Legacy scalar score functions — re-exported for backward compatibility.
# Canonical location: app.domain.transition.scoring.components.*
from app.domain.transition.scoring.components.bass import BassComponent
from app.domain.transition.scoring.components.drums import DrumsComponent
from app.domain.transition.scoring.components.harmonics import HarmonicsComponent
from app.domain.transition.scoring.components.vocals import VocalsComponent

score_drums_compat = DrumsComponent().score
score_bass_compat = BassComponent().score
score_harmonic_compat = HarmonicsComponent().score
score_vocal_compat = VocalsComponent().score

__all__ = [
    "NEURAL_MIX_STEMS",
    "TRANSITION_ENERGY_BIAS",
    "TRANSITION_STEM_WEIGHTS",
    "TRANSITION_TYPES",
    "NeuralMixScore",
    "NeuralMixScorer",
    "NeuralMixStem",
    "NeuralMixTransition",
    "score_bass_compat",
    "score_drums_compat",
    "score_harmonic_compat",
    "score_vocal_compat",
]
