"""Pydantic DTOs for deck control surface."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DeckStateRead(BaseModel):
    """Snapshot of one deck's runtime state."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "deck_id": 1,
                "state": "playing",
                "track_id": 42,
                "position_ms": 60000,
                "duration_ms": 240000,
                "pitch": 1.0,
                "gain": 1.0,
            }
        }
    )

    deck_id: int
    state: str = Field(description="empty|loading|loaded|cueing|playing|looping|paused|unloading")
    track_id: int | None = None
    position_ms: int = 0
    duration_ms: int = 0
    pitch: float = 1.0
    gain: float = 1.0


class DeckLoadRequest(BaseModel):
    deck_id: int = Field(ge=1, le=4)
    track_id: int


class DeckPitchRequest(BaseModel):
    deck_id: int = Field(ge=1, le=4)
    pitch: float = Field(ge=0.92, le=1.08, description="±8% DJ standard")


class DeckGainRequest(BaseModel):
    deck_id: int = Field(ge=1, le=4)
    gain: float = Field(ge=0.0, le=1.5)
