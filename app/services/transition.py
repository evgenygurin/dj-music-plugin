"""Backward-compatibility shim — real code lives in app.transition.

This module re-exports all public symbols so existing imports continue working.
Will be removed in Phase 5 (cleanup).
"""

from app.entities.audio.features import TrackFeatures as TrackFeatures
from app.transition.scorer import TransitionScore as TransitionScore
from app.transition.scorer import TransitionScorer as TransitionScorer
