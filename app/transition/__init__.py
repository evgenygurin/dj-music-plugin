"""Transition scoring domain — pure math, no I/O."""

from app.transition.math_helpers import bpm_distance, correlation, cosine_similarity
from app.transition.recipe import TransitionRecipe, TransitionType
from app.transition.scorer import (
    TransitionScore,
    TransitionScorer,
    recommend_style,
    style_profile,
)
from app.transition.section_context import SectionContext
from app.transition.style import recommend_recipe

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
