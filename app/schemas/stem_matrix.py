"""Structured-output model for stem_matrix tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ActiveStem(BaseModel):
    model_config = ConfigDict(frozen=True)

    deck_index: int
    stem_type: str
    track_id: int


class MatrixFrame(BaseModel):
    model_config = ConfigDict(frozen=True)

    time_s: float
    active_decks: list[ActiveStem] = Field(default_factory=list)
    fade_outs: int = 0
    fade_ins: int = 0


class StemMatrixResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_duration_s: float
    frame_count: int
    target_bpm: float
    frames: list[MatrixFrame] = Field(default_factory=list)
