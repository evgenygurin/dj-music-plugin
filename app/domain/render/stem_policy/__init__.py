"""Stem transition policy engine.

A pluggable policy engine for per-stem fade decisions during render.
Each policy is a pure function that takes a FadePlan and a
StemTransitionContext and returns an updated FadePlan.
"""

from app.domain.render.stem_policy.base import (
    CompositeStemTransitionPolicy,
    default_policy,
)
from app.domain.render.stem_policy.builder import build_default_policy
from app.domain.render.stem_policy.context import TrackRenderContext, TrackRenderContextBuilder
from app.domain.render.stem_policy.models import (
    AvailableData,
    FadePlan,
    StemTransitionCacheKey,
    StemTransitionContext,
    StemTransitionPolicy,
)

__all__ = [
    "AvailableData",
    "CompositeStemTransitionPolicy",
    "FadePlan",
    "StemTransitionCacheKey",
    "StemTransitionContext",
    "StemTransitionPolicy",
    "TrackRenderContext",
    "TrackRenderContextBuilder",
    "build_default_policy",
    "default_policy",
]
