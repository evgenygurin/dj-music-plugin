"""TrackAffinity DTOs — synced with prod schema 2026-05-07.

Counter columns are now ``like_count`` / ``ban_count`` / ``skip_count``
(per the prod table) and a denormalised ``net_sentiment`` float, plus
``last_played_at``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TrackAffinityView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    track_a_id: int
    track_b_id: int
    play_count: int = 0
    avg_score: float | None = None
    like_count: int = 0
    ban_count: int = 0
    skip_count: int = 0
    net_sentiment: float = 0.0
    last_played_at: datetime | None = None


class TrackAffinityFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
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
    like_count__gte: int | None = None
    like_count__lte: int | None = None
    ban_count__gte: int | None = None
    ban_count__lte: int | None = None
    skip_count__gte: int | None = None
    skip_count__lte: int | None = None
    net_sentiment__gte: float | None = None
    net_sentiment__lte: float | None = None
    net_sentiment__range: list[float] | None = None


class TrackAffinityCreate(BaseModel):
    """Explicit creation rare — usually derived via feedback handler."""

    model_config = ConfigDict(extra="forbid")
    track_a_id: int
    track_b_id: int
    avg_score: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_distinct_endpoints(self) -> Self:
        # Audit iter 54 (T-52): an affinity row between a track and
        # itself is degenerate — there's no "pair history" to record.
        if self.track_a_id == self.track_b_id:
            raise ValueError(
                f"track_a_id and track_b_id must differ; got {self.track_a_id} for both"
            )
        return self


class TrackAffinityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    avg_score: float | None = Field(default=None, ge=0.0, le=1.0)
    play_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    ban_count: int | None = Field(default=None, ge=0)
    skip_count: int | None = Field(default=None, ge=0)
    net_sentiment: float | None = Field(default=None, ge=-1.0, le=1.0)
    last_played_at: datetime | None = None
