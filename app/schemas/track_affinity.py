"""TrackAffinity DTOs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TrackAffinityView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    track_a_id: int
    track_b_id: int
    play_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    avg_score: float | None = None


class TrackAffinityFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Audit iter 41 (T-39): canonical id-range / batch lookups + the
    # symmetric ``__in`` / ``__lte`` ops missing on the existing pair
    # filters. ``play_count`` / ``positive_count`` / ``negative_count``
    # are how the affinity score is actually computed — filtering by
    # them is the only way to find "pairs played 10+ times" or
    # "pairs with all-positive feedback".
    id__eq: int | None = None
    id__in: list[int] | None = None
    id__gt: int | None = None
    id__gte: int | None = None
    id__lt: int | None = None
    id__lte: int | None = None
    track_a_id__eq: int | None = None
    track_a_id__in: list[int] | None = None
    track_b_id__eq: int | None = None
    track_b_id__in: list[int] | None = None
    avg_score__gte: float | None = None
    avg_score__lte: float | None = None
    avg_score__range: list[float] | None = None
    play_count__gte: int | None = None
    play_count__lte: int | None = None
    positive_count__gte: int | None = None
    positive_count__lte: int | None = None
    negative_count__gte: int | None = None
    negative_count__lte: int | None = None


class TrackAffinityCreate(BaseModel):
    """Explicit creation rare — usually derived via ``refresh`` handler."""

    model_config = ConfigDict(extra="forbid")
    track_a_id: int
    track_b_id: int
    avg_score: float | None = Field(default=None, ge=0.0, le=1.0)


class TrackAffinityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    avg_score: float | None = Field(default=None, ge=0.0, le=1.0)
    play_count: int | None = Field(default=None, ge=0)
    # Audit iter 41: callers writing affinity feedback need a path to
    # increment positive/negative counts directly. Without these,
    # counts could only be moved through the implicit refresh handler,
    # blocking explicit recalibration.
    positive_count: int | None = Field(default=None, ge=0)
    negative_count: int | None = Field(default=None, ge=0)
