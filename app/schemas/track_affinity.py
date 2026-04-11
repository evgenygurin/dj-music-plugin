"""Pydantic DTOs for track affinity."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TrackAffinityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    track_a_id: int
    track_b_id: int
    play_count: int
    avg_score: float | None
    like_count: int
    ban_count: int
    skip_count: int
    net_sentiment: float
    last_played_at: datetime | None


class AffinityRecommendation(BaseModel):
    track_id: int
    net_sentiment: float
    play_count: int
    avg_score: float | None
