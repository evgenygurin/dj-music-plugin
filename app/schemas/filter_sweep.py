"""Structured-output model for filter_sweep_builder tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FilterSweepSide(BaseModel):
    model_config = ConfigDict(frozen=True)

    start_freq_hz: float
    end_freq_hz: float
    direction: str
    curve: str
    resonance: float
    ffmpeg_expr: str | None = None


class FilterSweepResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    preset_name: str | None = None
    outgoing: FilterSweepSide | None = None
    incoming: FilterSweepSide | None = None
