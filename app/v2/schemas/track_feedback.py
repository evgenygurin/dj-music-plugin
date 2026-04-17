"""TrackFeedback DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TrackFeedbackView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    track_id: int
    kind: Literal["like", "ban", "rate"]
    rating: int | None = None
    notes: str | None = None


class TrackFeedbackFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id__eq: int | None = None
    track_id__in: list[int] | None = None
    kind__eq: Literal["like", "ban", "rate"] | None = None


class TrackFeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id: int
    kind: Literal["like", "ban", "rate"]
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None


class TrackFeedbackUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None
