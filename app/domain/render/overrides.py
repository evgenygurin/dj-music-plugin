from __future__ import annotations

from dataclasses import dataclass, replace

from app.domain.render.models import RenderPlan


@dataclass(frozen=True, slots=True)
class RenderRequestOverrides:
    hpf_cutoff_hz: float | None = None
    per_track_eq_mid_cut_db: float | None = None
    per_track_eq_bright_boost_db: float | None = None
    pre_comp_threshold_db: float | None = None
    pre_comp_ratio: float | None = None
    pre_comp_attack_ms: float | None = None
    pre_comp_release_ms: float | None = None
    glue_comp_threshold_db: float | None = None
    glue_comp_ratio: float | None = None
    glue_comp_attack_ms: float | None = None
    glue_comp_release_ms: float | None = None
    master_eq_air_boost_db: float | None = None
    master_eq_mud_cut_db: float | None = None
    master_eq_sub_boost_db: float | None = None
    limiter_attack_ms: float | None = None
    limiter_release_ms: float | None = None
    limiter_ceiling: float | None = None
    dynaudnorm_maxgain: float | None = None
    xsplit_low_hz: int | None = None
    xsplit_high_hz: int | None = None
    eq_phase_1_ratio: float | None = None
    eq_phase_2_ratio: float | None = None
    low_swap_beats: float | None = None
    outro_fade_bars: int | None = None


def apply_overrides(plan: RenderPlan, overrides: RenderRequestOverrides) -> RenderPlan:
    kwargs: dict[str, object] = {}
    for field_name in overrides.__dataclass_fields__:
        value = getattr(overrides, field_name)
        if value is not None:
            kwargs[field_name] = value
    if not kwargs:
        return plan
    return replace(plan, **kwargs)
