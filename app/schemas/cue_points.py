"""Structured-output model for cue_points tool."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CueItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int
    cue_type: str
    position_ms: int
    label: str
    color: str


class CuePointsResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    track_id: int
    bpm: float = 0.0
    cues: list[CueItem] = Field(default_factory=list)
