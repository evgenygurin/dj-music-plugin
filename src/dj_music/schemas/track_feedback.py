"""Pydantic DTOs for track feedback."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TrackFeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    track_id: int
    rating: int
    status: str
    notes: str | None
    play_count: int
    skip_count: int


class TrackFeedbackUpdate(BaseModel):
    rating: int | None = Field(None, ge=1, le=5)
    status: str | None = None
    notes: str | None = None
