"""Structured-output model for subgenre_preset tool."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SubgenrePresetResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    subgenre: str
    transition_bars: int
    body_bars: int
    xsplit_low_hz: int
    xsplit_high_hz: int
    eq_phase_1_ratio: float
    eq_phase_2_ratio: float
    low_swap_beats: float
    outro_fade_bars: int
    hpf_cutoff_hz: float
    per_track_eq_mid_cut_db: float
    per_track_eq_bright_boost_db: float
    pre_comp_threshold_db: float
    pre_comp_ratio: float
    glue_comp_threshold_db: float
    glue_comp_ratio: float
    master_eq_air_boost_db: float
    master_eq_mud_cut_db: float
    master_eq_sub_boost_db: float
    limiter_ceiling: float
    limiter_attack_ms: float
    limiter_release_ms: float
    dynaudnorm_maxgain: float
