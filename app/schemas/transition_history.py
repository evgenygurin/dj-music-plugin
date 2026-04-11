"""Pydantic DTOs for transition history."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TransitionHistoryCreate(BaseModel):
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
    user_reaction: str | None = None
    session_id: str | None = None


class TransitionHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    from_track_id: int
    to_track_id: int
    overall_score: float | None
    bpm_score: float | None
    harmonic_score: float | None
    energy_score: float | None
    spectral_score: float | None
    groove_score: float | None
    timbral_score: float | None
    style: str | None
    duration_sec: float | None
    tempo_match_ratio: float | None
    user_reaction: str | None
    session_id: str | None
    created_at: datetime


class BestPairRead(BaseModel):
    track_id: int
    play_count: int
    avg_score: float
    last_reaction: str | None
