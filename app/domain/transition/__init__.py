"""Transition scoring domain — pure math, no I/O."""

from app.domain.transition.math_helpers import bpm_distance, correlation, cosine_similarity
from app.domain.transition.scorer import (
    TransitionScore,
    TransitionScorer,
    recommend_style,
    style_profile,
)
from app.domain.transition.section_context import SectionContext

__all__ = [
    "SectionContext",
    "TransitionScore",
    "TransitionScorer",
    "bpm_distance",
    "correlation",
    "cosine_similarity",
    "recommend_style",
    "style_profile",
]
