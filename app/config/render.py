"""Render pipeline settings (beatmatch + EQ bass-swap mixdown)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RenderSettings(BaseSettings):
    """Musical + DSP constants for the render engine.

    Removes the magic numbers that were inline in
    ``generated-sets/hypnotic-roller-90-FINAL/render_pipeline.py``.
    """

    model_config = SettingsConfigDict(
        env_prefix="DJ_RENDER_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    target_bpm: float = Field(default=130.0, gt=0, description="All tracks stretched to this.")
    transition_bars: int = Field(default=32, gt=0, description="Overlap length between tracks.")
    body_bars: int = Field(default=24, gt=0, description="Solo time per track between blends.")
    xsplit_hz: int = Field(default=180, gt=0, description="Low/high crossover for the bass swap.")
    low_swap_beats: float = Field(
        default=1.0, gt=0, description="Low-band crossfade window (beats)."
    )
    transition_bars_hypnotic: int | None = Field(default=None, gt=0)
    transition_bars_minimal: int | None = Field(default=None, gt=0)
    transition_bars_melodic: int | None = Field(default=None, gt=0)
    transition_bars_peak_time: int | None = Field(default=None, gt=0)
    transition_bars_hard: int | None = Field(default=None, gt=0)
    transition_bars_acid: int | None = Field(default=None, gt=0)
    transition_bars_industrial: int | None = Field(default=None, gt=0)
    body_bars_hypnotic: int | None = Field(default=None, gt=0)
    body_bars_minimal: int | None = Field(default=None, gt=0)
    body_bars_melodic: int | None = Field(default=None, gt=0)
    body_bars_peak_time: int | None = Field(default=None, gt=0)
    body_bars_hard: int | None = Field(default=None, gt=0)
    body_bars_acid: int | None = Field(default=None, gt=0)
    body_bars_industrial: int | None = Field(default=None, gt=0)
    outro_fade_bars: int = Field(default=12, gt=0, description="End-of-mix fade length (bars).")
    limiter_ceiling: float = Field(
        default=0.85, gt=0, le=1.0, description="alimiter limit (-1.4 dBFS headroom)."
    )
    workspace_subdir: str = Field(
        default="render", description="Subdir under DeliverySettings.output_dir for job files."
    )

    @property
    def beat_s(self) -> float:
        """One beat in seconds at the target tempo."""
        return 60.0 / self.target_bpm

    @property
    def bar_s(self) -> float:
        """One 4/4 bar in seconds."""
        return 4.0 * self.beat_s
