"""Transition scoring domain — pure math, no I/O."""

from app.domain.transition.math_helpers import bpm_distance, correlation, cosine_similarity
from app.domain.transition.recipe import TransitionRecipe, TransitionType
from app.domain.transition.scorer import (
    TransitionScore,
    TransitionScorer,
    recommend_style,
    style_profile,
)
from app.domain.transition.section_context import SectionContext
from app.domain.transition.style import recommend_recipe

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
