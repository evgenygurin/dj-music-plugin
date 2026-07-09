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
    xsplit_low_hz: int = Field(default=250, gt=0, description="Low/mid crossover.")
    xsplit_high_hz: int = Field(default=4000, gt=0, description="Mid/high crossover.")
    eq_phase_1_ratio: float = Field(
        default=0.40, gt=0, le=1.0, description="Fraction of transition for HIGH phase."
    )
    eq_phase_2_ratio: float = Field(
        default=0.70, gt=0, le=1.0, description="Fraction of transition for MID phase."
    )
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
        default=0.93, gt=0, le=1.0, description="alimiter limit (-0.45 dBFS headroom)."
    )

    # ── Per-track pre-processing ──
    hpf_cutoff_hz: float = Field(
        default=30.0, gt=0, description="Subsonic highpass filter cutoff."
    )
    per_track_eq_mid_cut_db: float = Field(
        default=-1.0, le=0, description="300-500Hz mid cut for all tracks."
    )
    per_track_eq_bright_boost_db: float = Field(
        default=1.5, ge=0, description="8-12kHz boost for dark tracks (centroid < 2000 Hz)."
    )
    pre_comp_threshold_db: float = Field(default=-18.0, description="Pre-compressor threshold.")
    pre_comp_ratio: float = Field(default=3.0, gt=1, description="Pre-compressor ratio.")
    pre_comp_attack_ms: float = Field(default=10.0, gt=0, description="Pre-compressor attack.")
    pre_comp_release_ms: float = Field(default=80.0, gt=0, description="Pre-compressor release.")

    # ── Master bus ──
    glue_comp_threshold_db: float = Field(default=-18.0, description="Glue compressor threshold.")
    glue_comp_ratio: float = Field(default=3.0, gt=1, description="Glue compressor ratio.")
    glue_comp_attack_ms: float = Field(default=30.0, gt=0, description="Glue compressor attack.")
    glue_comp_release_ms: float = Field(
        default=150.0, gt=0, description="Glue compressor release."
    )
    master_eq_air_boost_db: float = Field(
        default=1.5, ge=0, description="10-12kHz high shelf boost."
    )
    master_eq_mud_cut_db: float = Field(
        default=-1.0, le=0, description="200-400Hz mud cut."
    )
    master_eq_sub_boost_db: float = Field(
        default=0.5, ge=0, description="60-80Hz sub weight boost."
    )
    limiter_attack_ms: float = Field(default=10.0, gt=0, description="alimiter attack (ms) — slower = more punch.")
    limiter_release_ms: float = Field(default=30.0, gt=0, description="alimiter release (ms).")
    dynaudnorm_maxgain: float = Field(default=2.0, ge=0, description="dynaudnorm maxgain (was 6).")

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
