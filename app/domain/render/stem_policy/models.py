"""Core data models for stem transition policy engine."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Protocol, runtime_checkable

from app.domain.render.models import StemSegment


@dataclass(frozen=True)
class AvailableData:
    """Flags indicating which track data is available for policy decisions."""

    analysis_levels_in: tuple[int, ...] = ()
    analysis_levels_out: tuple[int, ...] = ()
    has_beatgrid: bool = False
    has_cue_points: bool = False
    has_sections: bool = False
    has_stem_features: bool = False
    has_transition_recipe: bool = False
    has_affinity: bool = False
    has_user_feedback: bool = False
    has_embedding: bool = False
    has_cross_similarity: bool = False
    has_ym_metadata: bool = False
    has_beatport: bool = False
    has_transition_history: bool = False

    def update(self, **kwargs: Any) -> AvailableData:
        """Return a new instance with the given fields replaced."""
        return replace(self, **kwargs)


@dataclass(frozen=True)
class StemTransitionContext:
    """Context for computing stem-specific fade plan.

    Contains all per-track, per-stem data needed for policy decisions.
    """

    stem: str
    track_input: dict[str, Any]
    track_features_in: dict[str, Any] | None = None
    track_features_out: dict[str, Any] | None = None
    stem_features_in: dict[str, Any] | None = None
    stem_features_out: dict[str, Any] | None = None
    segment: StemSegment | None = None
    base_d_in_s: float = 8.0
    base_d_out_s: float = 8.0
    target_bpm: float = 130.0
    available: AvailableData | None = None
    is_first: bool = False
    is_last: bool = False

    def __post_init__(self) -> None:
        """Ensure available is set to a default if not provided."""
        if self.available is None:
            object.__setattr__(self, "available", AvailableData())


@dataclass(frozen=True)
class FadePlan:
    """Per-stem fade parameters computed by a policy."""

    fade_in_s: float | None = None
    fade_in_curve: str = "qsin"
    fade_out_s: float | None = None
    fade_out_curve: str = "qsin"
    hpf_hz: int | None = None
    gain_db: float = 0.0
    pinpoint_s: float | None = None
    pinpoint_curve: str | None = None
    notes: tuple[str, ...] = ()

    @staticmethod
    def identity() -> FadePlan:
        """Return neutral default fade plan."""
        return FadePlan()

    def update(self, **kwargs: Any) -> FadePlan:
        """Return a new instance with the given fields replaced."""
        return replace(self, **kwargs)


@runtime_checkable
class StemTransitionPolicy(Protocol):
    """Protocol for stem-specific transition policies."""

    name: str

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        """Merge policy output into the existing fade plan."""
        ...


@dataclass(frozen=True)
class StemTransitionCacheKey:
    """Cache key for memoizing computed fade plans."""

    track_in_id: int
    track_out_id: int
    stem: str

    def __hash__(self) -> int:
        return hash((self.track_in_id, self.track_out_id, self.stem))
