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
    track_a_id__eq: int | None = None
    track_b_id__eq: int | None = None
    avg_score__gte: float | None = None


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
