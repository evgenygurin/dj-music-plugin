"""Public API for the app.transition package."""

from app.transition.math_helpers import bpm_distance, correlation, cosine_similarity
from app.transition.models import (
    ConstraintResult,
    SectionContext,
    TransitionRecommendation,
    TransitionScore,
)
from app.transition.recommender import TransitionRecommender
from app.transition.scorer import TransitionScorer
from app.transition.types import Stem, StemAction, TransitionIntent

__all__ = [
    "ConstraintResult",
    "SectionContext",
    "Stem",
    "StemAction",
    "TransitionIntent",
    "TransitionRecommendation",
    "TransitionRecommender",
    "TransitionScore",
    "TransitionScorer",
    "bpm_distance",
    "correlation",
    "cosine_similarity",
]
