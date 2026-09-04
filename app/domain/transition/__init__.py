"""Transition scoring domain — pure math, no I/O.

Public surface (post Neural Mix refactor):

* ``TransitionScorer`` / ``TransitionScore`` — the six-component scorer
  (BPM + energy + four Neural Mix stem compats).
* ``NeuralMixTransition`` — the eight Neural Mix presets:
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

from app.domain.transition.builders import build_recipe
from app.domain.transition.dj_mixing import (
    ALIGNMENT_DEFAULT_WEIGHTS,
    MIXING_DEFAULT_TARGET_BARS,
    MIXING_DEFAULT_TRANSITION_BARS,
    MIXING_MAX_TRANSITION_BARS,
    MIXING_MIN_TRANSITION_BARS,
    S_BEAT_SIGMA_S,
    S_DRIFT_MAX_S,
    S_DRIFT_SIGMA_S,
    S_PHRASE_SIGMA_S,
    S_TEMPO_SIGMA,
    AlignmentScore,
    TempoModel,
    TransitionCue,
    TransitionGrid,
    compute_alignment,
    generate_transition_cues,
    score_beat_alignment,
    score_drift,
    score_phrase_alignment,
    score_tempo,
    select_transition_bars,
)
from app.domain.transition.math_helpers import bpm_distance, correlation, cosine_similarity
from app.domain.transition.neural_mix import (
    NeuralMixScore,
    NeuralMixScorer,
    NeuralMixStem,
    NeuralMixTransition,
)
from app.domain.transition.picker import (
    PickerDecision,
    build_recipe_for_pair,
    pick_neural_mix,
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
    "ALIGNMENT_DEFAULT_WEIGHTS",
    "DEFAULT_TRANSITION_BARS",
    "LEVEL_SILENT",
    "LEVEL_UNITY",
    "MIXING_DEFAULT_TARGET_BARS",
    "MIXING_DEFAULT_TRANSITION_BARS",
    "MIXING_MAX_TRANSITION_BARS",
    "MIXING_MIN_TRANSITION_BARS",
    "S_BEAT_SIGMA_S",
    "S_DRIFT_MAX_S",
    "S_DRIFT_SIGMA_S",
    "S_PHRASE_SIGMA_S",
    "S_TEMPO_SIGMA",
    "AlignmentScore",
    "MuteFXEvent",
    "MuteFXTrigger",
    "NeuralMixRecipe",
    "NeuralMixScore",
    "NeuralMixScorer",
    "NeuralMixStem",
    "NeuralMixTransition",
    "PickerDecision",
    "SectionContext",
    "StemKeyframe",
    "TempoModel",
    "TransitionCue",
    "TransitionGrid",
    "TransitionScore",
    "TransitionScorer",
    "bpm_distance",
    "build_recipe",
    "build_recipe_for_pair",
    "compute_alignment",
    "correlation",
    "cosine_similarity",
    "generate_transition_cues",
    "pick_neural_mix",
    "score_beat_alignment",
    "score_drift",
    "score_phrase_alignment",
    "score_tempo",
    "select_transition_bars",
]
