"""Transition scoring settings (weights, thresholds, cache)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TransitionSettings(BaseSettings):
    """6-component scoring weights + hard constraints + cache."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_TRANSITION_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    weight_bpm: float = Field(default=0.20, ge=0.0, le=1.0)
    weight_harmonic: float = Field(default=0.12, ge=0.0, le=1.0)
    weight_energy: float = Field(default=0.18, ge=0.0, le=1.0)
    weight_spectral: float = Field(default=0.20, ge=0.0, le=1.0)
    weight_groove: float = Field(default=0.15, ge=0.0, le=1.0)
    weight_timbral: float = Field(default=0.15, ge=0.0, le=1.0)

    hard_reject_bpm_diff: float = Field(default=10.0, ge=0.0, le=100.0)
    hard_reject_camelot_dist: int = Field(default=5, ge=0, le=12)
    hard_reject_energy_gap_lufs: float = Field(default=6.0, ge=0.0, le=30.0)

    cache_ttl_s: int = Field(default=3600, ge=0)
    cache_max_size: int = Field(default=10_000, ge=100)

    scoring_bpm_confidence_floor: float = Field(default=0.3, ge=0.0, le=1.0)
    variable_tempo_penalty: float = Field(default=0.05, ge=0.0, le=0.5)

    # Mirror of legacy scoring_* fields (app/config.py) — consumed by
    # app/v2/domain/transition/components/{bpm,energy}.py. Defaults match
    # legacy 1:1 to preserve numeric parity.
    scoring_variable_tempo_penalty: float = Field(default=0.15, ge=0.0, le=1.0)
    scoring_lra_diff_penalty_threshold: float = Field(default=8.0, ge=0.0, le=30.0)
    scoring_lra_diff_penalty: float = Field(default=0.10, ge=0.0, le=1.0)
    scoring_crest_diff_penalty_threshold: float = Field(default=10.0, ge=0.0, le=50.0)
    scoring_crest_diff_penalty: float = Field(default=0.10, ge=0.0, le=1.0)
    scoring_energy_slope_bonus: float = Field(default=0.05, ge=0.0, le=1.0)

    # ── Phase 2 feature flags ──
    # Enable the FILTER_SWEEP preset in the Neural Mix picker.
    # When False, HYPNOTIC_PAIR routes to the default ECHO_OUT instead.
    enable_filter_sweep_style: bool = Field(default=True)
