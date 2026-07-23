"""Structured-output model for transition_window tool."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TransitionWindowResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    from_track_id: int
    to_track_id: int
    mix_out_start_ms: int
    mix_out_end_ms: int
    mix_in_start_ms: int
    mix_in_end_ms: int
    recommendation: str
