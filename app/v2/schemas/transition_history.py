"""TransitionHistory DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TransitionHistoryView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    from_track_id: int
    to_track_id: int
    set_id: int | None = None
    overall_score: float | None = None
    style: str | None = None
    reaction: Literal["positive", "neutral", "negative"] | None = None
    notes: str | None = None


class TransitionHistoryFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_track_id__eq: int | None = None
    to_track_id__eq: int | None = None
    reaction__eq: Literal["positive", "neutral", "negative"] | None = None
    overall_score__gte: float | None = None


class TransitionHistoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_track_id: int
    to_track_id: int
    set_id: int | None = None
    overall_score: float | None = Field(default=None, ge=0.0, le=1.0)
    style: str | None = None
    reaction: Literal["positive", "neutral", "negative"] | None = None
    notes: str | None = None


class TransitionHistoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reaction: Literal["positive", "neutral", "negative"] | None = None
    notes: str | None = None
