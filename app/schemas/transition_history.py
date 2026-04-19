"""TransitionHistory DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TransitionHistoryView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    from_track_id: int
    to_track_id: int
    overall_score: float | None = None
    bpm_score: float | None = None
    harmonic_score: float | None = None
    energy_score: float | None = None
    spectral_score: float | None = None
    groove_score: float | None = None
    timbral_score: float | None = None
    style: str | None = None
    duration_sec: float | None = None
    tempo_match_ratio: float | None = None
    user_reaction: Literal["positive", "neutral", "negative"] | None = None
    session_id: str | None = None


class TransitionHistoryFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_track_id__eq: int | None = None
    from_track_id__in: list[int] | None = None
    to_track_id__eq: int | None = None
    to_track_id__in: list[int] | None = None
    user_reaction__eq: Literal["positive", "neutral", "negative"] | None = None
    overall_score__gte: float | None = None
    session_id__eq: str | None = None


class TransitionHistoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_track_id: int
    to_track_id: int
    overall_score: float | None = Field(default=None, ge=0.0, le=1.0)
    bpm_score: float | None = None
    harmonic_score: float | None = None
    energy_score: float | None = None
    spectral_score: float | None = None
    groove_score: float | None = None
    timbral_score: float | None = None
    style: str | None = None
    duration_sec: float | None = None
    tempo_match_ratio: float | None = None
    user_reaction: Literal["positive", "neutral", "negative"] | None = None
    session_id: str | None = None


class TransitionHistoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_reaction: Literal["positive", "neutral", "negative"] | None = None
    style: str | None = None
    duration_sec: float | None = None
    tempo_match_ratio: float | None = None
