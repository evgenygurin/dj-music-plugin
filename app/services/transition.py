"""Backward-compatibility shim — real code lives in app.domain.transition.

This module re-exports all public symbols so existing imports continue working.
Will be removed in Phase 5 (cleanup).
"""

from app.core.track_features import TrackFeatures as TrackFeatures
from app.domain.transition.scorer import TransitionScore as TransitionScore
from app.domain.transition.scorer import TransitionScorer as TransitionScorer
