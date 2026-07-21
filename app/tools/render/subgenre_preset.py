"""subgenre_preset — render settings tailored to a techno subgenre."""
from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.tools import tool
from pydantic import Field

from app.domain.performance.subgenre_presets import PRESET_MAP, resolve_preset
from app.schemas.subgenre_preset import SubgenrePresetResult

VALID_SUBGENRES = Literal[
    "industrial_techno", "dub_techno", "hard_techno",
    "hypnotic_techno", "peak_time_techno", "driving_techno",
    "acid_techno", "raw_techno", "tribal_techno", "detroit_techno",
    "deep_techno", "minimal_techno", "progressive_techno",
    "melodic_techno",
]

SUBGENRE_NAMES: list[str] = list(PRESET_MAP.keys())


@tool(
    name="subgenre_preset",
    tags={"namespace:render:config"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Get the complete render settings preset for a techno subgenre. "
        "Returns 22 DSP parameters tuned for the subgenre's mixing style "
        "(industrial=aggressive compression, dub=long transitions, etc.). "
        "Use the returned subgenre name with render_mixdown's subgenre parameter."
    ),
    meta={"timeout_s": 5.0},
    timeout=5.0,
)
async def subgenre_preset(
    subgenre: Annotated[
        str,
        Field(description="Subgenre key: industrial_techno, dub_techno, etc."),
    ],
) -> SubgenrePresetResult:
    if subgenre not in PRESET_MAP:
        raise ValueError(
            f"unknown subgenre {subgenre!r}; valid: {sorted(SUBGENRE_NAMES)}"
        )
    preset = resolve_preset(subgenre)
    if preset is None:
        raise ValueError(f"no preset for {subgenre!r}")
    return SubgenrePresetResult(
        subgenre=subgenre,
        transition_bars=preset.transition_bars,
        body_bars=preset.body_bars,
        xsplit_low_hz=preset.xsplit_low_hz,
        xsplit_high_hz=preset.xsplit_high_hz,
        eq_phase_1_ratio=preset.eq_phase_1_ratio,
        eq_phase_2_ratio=preset.eq_phase_2_ratio,
        low_swap_beats=preset.low_swap_beats,
        outro_fade_bars=preset.outro_fade_bars,
        hpf_cutoff_hz=preset.hpf_cutoff_hz,
        per_track_eq_mid_cut_db=preset.per_track_eq_mid_cut_db,
        per_track_eq_bright_boost_db=preset.per_track_eq_bright_boost_db,
        pre_comp_threshold_db=preset.pre_comp_threshold_db,
        pre_comp_ratio=preset.pre_comp_ratio,
        glue_comp_threshold_db=preset.glue_comp_threshold_db,
        glue_comp_ratio=preset.glue_comp_ratio,
        master_eq_air_boost_db=preset.master_eq_air_boost_db,
        master_eq_mud_cut_db=preset.master_eq_mud_cut_db,
        master_eq_sub_boost_db=preset.master_eq_sub_boost_db,
        limiter_ceiling=preset.limiter_ceiling,
        limiter_attack_ms=preset.limiter_attack_ms,
        limiter_release_ms=preset.limiter_release_ms,
        dynaudnorm_maxgain=preset.dynaudnorm_maxgain,
    )
