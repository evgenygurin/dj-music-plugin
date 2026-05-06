"""Transition scoring domain — pure math, no I/O.

Public surface (post Neural Mix refactor):

* ``TransitionScorer`` / ``TransitionScore`` — the six-component scorer
  (BPM + energy + four Neural Mix stem compats).
* ``NeuralMixTransition`` — the seven djay Pro 5 Automix presets:
  FADE, ECHO_OUT, VOCAL_SUSTAIN, HARMONIC_SUSTAIN, DRUM_SWAP,
  VOCAL_CUT, DRUM_CUT.
* ``NeuralMixRecipe`` — stem-keyframe envelope describing one
  transition. Persisted as JSON in ``transitions.transition_recipe_json``.
* ``StemKeyframe``, ``MuteFXEvent``, ``MuteFXTrigger``, ``NeuralMixStem`` —
  recipe primitives.
* ``SectionContext`` — structural mix-window metadata used by the
  picker.
* Math helpers (``bpm_distance``, ``correlation``, ``cosine_similarity``).
"""

from app.domain.transition.math_helpers import bpm_distance, correlation, cosine_similarity
from app.domain.transition.neural_mix import (
    NeuralMixScore,
    NeuralMixScorer,
    NeuralMixStem,
    NeuralMixTransition,
)
from app.domain.transition.recipe import (
    DEFAULT_TRANSITION_BARS,
    LEVEL_SILENT,
    LEVEL_UNITY,
    MuteFXEvent,
    MuteFXTrigger,
    NeuralMixRecipe,
    StemKeyframe,
)
from app.domain.transition.score import TransitionScore
from app.domain.transition.scorer import TransitionScorer
from app.domain.transition.section_context import SectionContext

__all__ = [
    "DEFAULT_TRANSITION_BARS",
    "LEVEL_SILENT",
    "LEVEL_UNITY",
    "MuteFXEvent",
    "MuteFXTrigger",
    "NeuralMixRecipe",
    "NeuralMixScore",
    "NeuralMixScorer",
    "NeuralMixStem",
    "NeuralMixTransition",
    "SectionContext",
    "StemKeyframe",
    "TransitionScore",
    "TransitionScorer",
    "bpm_distance",
    "correlation",
    "cosine_similarity",
]
