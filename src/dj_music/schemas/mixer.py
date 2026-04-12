"""Pydantic DTOs for mixer control surface."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from dj_music.schemas.deck import DeckStateRead


class MixerStateRead(BaseModel):
    """Snapshot of mixer + all decks."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "crossfader": 0.5,
                "channel_gain": {"1": 1.0, "2": 1.0},
                "eq": {"1": {"low": 0.0, "mid": 0.0, "high": 0.0}},
                "filter": {"1": 20000.0},
                "decks": {},
            }
        }
    )

    crossfader: float
    channel_gain: dict[int, float]
    eq: dict[int, dict[str, float]] = Field(
        default_factory=dict, description="Per-deck 3-band EQ gain in dB (-40..6)"
    )
    filter: dict[int, float] = Field(
        default_factory=dict, description="Per-deck filter cutoff in Hz (20..20000)"
    )
    decks: dict[int, DeckStateRead]


class CrossfaderRequest(BaseModel):
    target: float = Field(ge=0.0, le=1.0, description="0=full A side, 1=full B side")
    duration_ms: int = Field(ge=0, le=60000, default=0, description="0=instant, >0=interpolate")


class ChannelGainRequest(BaseModel):
    deck_id: int = Field(ge=1, le=4)
    gain: float = Field(ge=0.0, le=1.5)
