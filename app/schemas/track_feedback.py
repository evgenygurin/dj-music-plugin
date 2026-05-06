"""TrackFeedback DTOs — synced with prod schema 2026-05-07.

Single row per ``track_id`` (UNIQUE on the table). Replaces the prior
``kind`` triplet (``like``/``ban``/``rate``) with ``status`` —
``active`` / ``liked`` / ``banned`` / ``archived`` — matching the prod
CHECK constraint and existing rows.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FeedbackStatus = Literal["active", "liked", "banned", "archived"]


class TrackFeedbackView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    track_id: int
    rating: int = 3
    status: FeedbackStatus = "active"
    notes: str | None = None
    play_count: int = 0
    skip_count: int = 0


class TrackFeedbackFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id__eq: int | None = None
    track_id__in: list[int] | None = None
    status__eq: FeedbackStatus | None = None
    status__in: list[FeedbackStatus] | None = None
    rating__eq: int | None = None
    rating__gte: int | None = None
    rating__lte: int | None = None
    rating__in: list[int] | None = None
    play_count__gte: int | None = None
    play_count__lte: int | None = None
    skip_count__gte: int | None = None
    skip_count__lte: int | None = None


class TrackFeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id: int
    rating: int = Field(default=3, ge=1, le=5)
    status: FeedbackStatus = "active"
    notes: str | None = None
    play_count: int = Field(default=0, ge=0)
    skip_count: int = Field(default=0, ge=0)


class TrackFeedbackUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: int | None = Field(default=None, ge=1, le=5)
    status: FeedbackStatus | None = None
    notes: str | None = None
    play_count: int | None = Field(default=None, ge=0)
    skip_count: int | None = Field(default=None, ge=0)
