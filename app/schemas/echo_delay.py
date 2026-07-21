"""Structured-output model for echo_builder tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EchoResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    preset_name: str | None = None
    delay_ms: float
    decay: float
    taps: int
    wet_dry_ratio: float
    stereo_spread: float
    ffmpeg_aecho_expr: str
