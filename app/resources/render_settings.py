"""Full RenderSettings resource — all 30+ DSP defaults as JSON.

Auto-discovered by FastMCP FileSystemProvider from ``app/resources/``.
No existing files changed.

Usage: read resource ``reference://render/settings`` to see current defaults.
"""

from __future__ import annotations

from fastmcp.resources import resource

from app.config import get_settings
from app.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META, json_dump


@resource(
    "reference://render/settings",
    mime_type="application/json",
    tags={"namespace:reference"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def render_settings_resource() -> str:
    """All RenderSettings DSP constants (HPF, compressors, limiter, EQ, crossover, dynaudnorm)."""
    r = get_settings().render
    return json_dump(
        {
            "target_bpm": r.target_bpm,
            "transition_bars": r.transition_bars,
            "body_bars": r.body_bars,
            "xsplit_low_hz": r.xsplit_low_hz,
            "xsplit_high_hz": r.xsplit_high_hz,
            "eq_phase_1_ratio": r.eq_phase_1_ratio,
            "eq_phase_2_ratio": r.eq_phase_2_ratio,
            "low_swap_beats": r.low_swap_beats,
            "outro_fade_bars": r.outro_fade_bars,
            "hpf_cutoff_hz": r.hpf_cutoff_hz,
            "per_track_eq_mid_cut_db": r.per_track_eq_mid_cut_db,
            "per_track_eq_bright_boost_db": r.per_track_eq_bright_boost_db,
            "pre_comp_threshold_db": r.pre_comp_threshold_db,
            "pre_comp_ratio": r.pre_comp_ratio,
            "pre_comp_attack_ms": r.pre_comp_attack_ms,
            "pre_comp_release_ms": r.pre_comp_release_ms,
            "glue_comp_threshold_db": r.glue_comp_threshold_db,
            "glue_comp_ratio": r.glue_comp_ratio,
            "glue_comp_attack_ms": r.glue_comp_attack_ms,
            "glue_comp_release_ms": r.glue_comp_release_ms,
            "master_eq_air_boost_db": r.master_eq_air_boost_db,
            "master_eq_mud_cut_db": r.master_eq_mud_cut_db,
            "master_eq_sub_boost_db": r.master_eq_sub_boost_db,
            "limiter_attack_ms": r.limiter_attack_ms,
            "limiter_release_ms": r.limiter_release_ms,
            "limiter_ceiling": r.limiter_ceiling,
            "dynaudnorm_maxgain": r.dynaudnorm_maxgain,
        }
    )
