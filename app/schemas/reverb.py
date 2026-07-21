"""Structured-output model for reverb_builder tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ReverbResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    preset_name: str | None = None
    decay_s: float
    pre_delay_ms: float
    mix_ratio: float
    space: str
    sample_rate: int
    total_samples: int
    highpass_hz: float
    lowpass_hz: float
