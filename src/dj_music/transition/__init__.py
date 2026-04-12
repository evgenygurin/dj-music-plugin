"""Transition scoring domain — pure math, no I/O."""

from dj_music.transition.math_helpers import bpm_distance, correlation, cosine_similarity
from dj_music.transition.recipe import TransitionRecipe, TransitionType
from dj_music.transition.scorer import (
    TransitionScore,
    TransitionScorer,
    recommend_style,
    style_profile,
)
from dj_music.transition.section_context import SectionContext
from dj_music.transition.style import recommend_recipe

__all__ = [
    "SectionContext",
    "TransitionRecipe",
    "TransitionScore",
    "TransitionScorer",
    "TransitionType",
    "bpm_distance",
    "correlation",
    "cosine_similarity",
    "recommend_recipe",
    "recommend_style",
    "style_profile",
]
