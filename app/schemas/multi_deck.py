"""Structured-output model for multi_deck_plan tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DeckAssign(BaseModel):
    model_config = ConfigDict(frozen=True)

    deck_index: int
    track_id: int
    active_stems: list[str]
    gain_db: float
    lowpass_hz: float
    highpass_hz: float


class DeckWindow(BaseModel):
    model_config = ConfigDict(frozen=True)

    start_s: float
    end_s: float
    decks: list[DeckAssign]


class MultiDeckPlanResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_simultaneous: int
    target_bpm: float
    windows: list[DeckWindow] = Field(default_factory=list)
    ffmpeg_amix_graph: str = ""
