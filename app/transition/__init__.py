"""Public API for the app.transition package.

Import from here rather than from submodules to stay insulated from
internal reorganisation.
"""

from app.transition.math_helpers import bpm_distance, correlation, cosine_similarity
from app.transition.recipe import EQPlan, RecipeStep, TransitionRecipe
from app.transition.score import TransitionScore
from app.transition.scorer import TransitionScorer
from app.transition.section_context import SectionContext
from app.transition.selector import TransitionSelector
from app.transition.types import Stem, StemAction, SubgenrePairType, TransitionIntent

__all__ = [
    "EQPlan",
    "RecipeStep",
    "SectionContext",
    "Stem",
    "StemAction",
    "SubgenrePairType",
    "TransitionIntent",
    "TransitionRecipe",
    "TransitionScore",
    "TransitionScorer",
    "TransitionSelector",
    "bpm_distance",
    "correlation",
    "cosine_similarity",
]
