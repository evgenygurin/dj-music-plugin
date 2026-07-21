"""Subgenre-aware render presets — maps MoodClassifier profiles to RenderSettings overrides.

Each techno subgenre needs different transition lengths, EQ curves, and effects.
Industrial wants aggressive 8-bar bass swaps; dub techno wants 64-bar hypnotic fades.

Wire: MoodClassifier(SubgenreProfile) → SubgenreRenderPreset → RenderSettings overrides.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config.render import RenderSettings


@dataclass(frozen=True, slots=True)
class SubgenreRenderPreset:
    """Per-subgenre tuning for the classic EQ bass-swap render engine.

    Overrides are applied on top of RenderSettings defaults via the handler's
    bar planning and render-planner assembly — subgenre-specific values
    take priority over the global defaults but can still be overridden by
    explicit user args (``transition_bars`` / ``body_bars`` kwargs).
    """

    transition_bars: int
    body_bars: int
    xsplit_low_hz: int = 250
    xsplit_high_hz: int = 4000
    eq_phase_1_ratio: float = 0.40
    eq_phase_2_ratio: float = 0.70
    low_swap_beats: float = 1.0
    outro_fade_bars: int = 12
    hpf_cutoff_hz: float = 30.0
    per_track_eq_mid_cut_db: float = -1.0
    per_track_eq_bright_boost_db: float = 1.5
    pre_comp_threshold_db: float = -18.0
    pre_comp_ratio: float = 3.0
    glue_comp_threshold_db: float = -14.0
    glue_comp_ratio: float = 3.0
    master_eq_air_boost_db: float = 1.5
    master_eq_mud_cut_db: float = -1.0
    master_eq_sub_boost_db: float = 0.5
    limiter_ceiling: float = 0.85
    limiter_attack_ms: float = 10.0
    limiter_release_ms: float = 30.0
    dynaudnorm_maxgain: float = 2.0

    def apply(self, settings: RenderSettings) -> None:
        """Mutate a RenderSettings instance with subgenre-specific values."""
        for field_name in self.__slots__:
            val = getattr(self, field_name)
            if val is not None and hasattr(settings, field_name):
                setattr(settings, field_name, val)


# ── Preset library ──────────────────────────────────────────

INDUSTRIAL = SubgenreRenderPreset(
    transition_bars=16,
    body_bars=48,
    xsplit_low_hz=300,
    xsplit_high_hz=5000,
    eq_phase_1_ratio=0.25,
    eq_phase_2_ratio=0.50,
    low_swap_beats=0.5,
    outro_fade_bars=8,
    hpf_cutoff_hz=35.0,
    per_track_eq_mid_cut_db=-1.5,
    per_track_eq_bright_boost_db=2.0,
    pre_comp_threshold_db=-15.0,
    pre_comp_ratio=3.0,
    glue_comp_threshold_db=-12.0,
    glue_comp_ratio=2.5,
    master_eq_air_boost_db=1.5,
    master_eq_mud_cut_db=-1.5,
    master_eq_sub_boost_db=0.75,
    limiter_ceiling=0.85,
    limiter_attack_ms=8.0,
    limiter_release_ms=25.0,
    dynaudnorm_maxgain=1.8,
)

DUB_TECHNO = SubgenreRenderPreset(
    transition_bars=64,
    body_bars=32,
    xsplit_low_hz=200,
    xsplit_high_hz=3500,
    eq_phase_1_ratio=0.60,
    eq_phase_2_ratio=0.85,
    low_swap_beats=2.0,
    outro_fade_bars=24,
    hpf_cutoff_hz=25.0,
    per_track_eq_mid_cut_db=0.0,
    per_track_eq_bright_boost_db=0.5,
    pre_comp_threshold_db=-14.0,
    pre_comp_ratio=2.0,
    glue_comp_threshold_db=-12.0,
    glue_comp_ratio=2.0,
    master_eq_air_boost_db=0.5,
    master_eq_mud_cut_db=0.0,
    master_eq_sub_boost_db=1.5,
    limiter_ceiling=0.88,
    limiter_attack_ms=15.0,
    limiter_release_ms=50.0,
    dynaudnorm_maxgain=3.0,
)

HARD_TECHNO = SubgenreRenderPreset(
    transition_bars=8,
    body_bars=64,
    xsplit_low_hz=350,
    xsplit_high_hz=5500,
    eq_phase_1_ratio=0.20,
    eq_phase_2_ratio=0.40,
    low_swap_beats=0.25,
    outro_fade_bars=4,
    hpf_cutoff_hz=40.0,
    per_track_eq_mid_cut_db=-3.0,
    per_track_eq_bright_boost_db=3.0,
    pre_comp_threshold_db=-22.0,
    pre_comp_ratio=5.0,
    glue_comp_threshold_db=-18.0,
    glue_comp_ratio=5.0,
    master_eq_air_boost_db=2.5,
    master_eq_mud_cut_db=-2.5,
    master_eq_sub_boost_db=1.5,
    limiter_ceiling=0.75,
    limiter_attack_ms=4.0,
    limiter_release_ms=15.0,
    dynaudnorm_maxgain=1.0,
)

HYPNOTIC = SubgenreRenderPreset(
    transition_bars=48,
    body_bars=40,
    xsplit_low_hz=220,
    xsplit_high_hz=3800,
    eq_phase_1_ratio=0.55,
    eq_phase_2_ratio=0.80,
    low_swap_beats=2.0,
    outro_fade_bars=16,
    hpf_cutoff_hz=28.0,
    per_track_eq_mid_cut_db=-0.5,
    per_track_eq_bright_boost_db=1.0,
    pre_comp_threshold_db=-16.0,
    pre_comp_ratio=2.5,
    glue_comp_threshold_db=-13.0,
    glue_comp_ratio=2.5,
    master_eq_air_boost_db=1.0,
    master_eq_mud_cut_db=-0.5,
    master_eq_sub_boost_db=1.0,
    limiter_ceiling=0.85,
    limiter_attack_ms=12.0,
    limiter_release_ms=40.0,
    dynaudnorm_maxgain=2.5,
)

PEAK_TIME = SubgenreRenderPreset(
    transition_bars=32,
    body_bars=32,
    xsplit_low_hz=260,
    xsplit_high_hz=4200,
    eq_phase_1_ratio=0.40,
    eq_phase_2_ratio=0.70,
    low_swap_beats=1.0,
    outro_fade_bars=12,
    hpf_cutoff_hz=30.0,
    per_track_eq_mid_cut_db=-1.0,
    per_track_eq_bright_boost_db=1.5,
    pre_comp_threshold_db=-18.0,
    pre_comp_ratio=3.0,
    glue_comp_threshold_db=-14.0,
    glue_comp_ratio=3.0,
    master_eq_air_boost_db=1.5,
    master_eq_mud_cut_db=-1.0,
    master_eq_sub_boost_db=0.5,
    limiter_ceiling=0.85,
    limiter_attack_ms=10.0,
    limiter_release_ms=30.0,
    dynaudnorm_maxgain=2.0,
)

DRIVING = SubgenreRenderPreset(
    transition_bars=24,
    body_bars=40,
    xsplit_low_hz=280,
    xsplit_high_hz=4500,
    eq_phase_1_ratio=0.35,
    eq_phase_2_ratio=0.65,
    low_swap_beats=0.75,
    outro_fade_bars=10,
    hpf_cutoff_hz=32.0,
    per_track_eq_mid_cut_db=-1.5,
    per_track_eq_bright_boost_db=2.0,
    pre_comp_threshold_db=-19.0,
    pre_comp_ratio=3.5,
    glue_comp_threshold_db=-15.0,
    glue_comp_ratio=3.5,
    master_eq_air_boost_db=2.0,
    master_eq_mud_cut_db=-1.5,
    master_eq_sub_boost_db=0.75,
    limiter_ceiling=0.82,
    limiter_attack_ms=8.0,
    limiter_release_ms=25.0,
    dynaudnorm_maxgain=1.8,
)

ACID = SubgenreRenderPreset(
    transition_bars=16,
    body_bars=56,
    xsplit_low_hz=270,
    xsplit_high_hz=5000,
    eq_phase_1_ratio=0.30,
    eq_phase_2_ratio=0.55,
    low_swap_beats=0.5,
    outro_fade_bars=8,
    hpf_cutoff_hz=35.0,
    per_track_eq_mid_cut_db=-2.0,
    per_track_eq_bright_boost_db=2.5,
    pre_comp_threshold_db=-20.0,
    pre_comp_ratio=4.0,
    glue_comp_threshold_db=-16.0,
    glue_comp_ratio=4.0,
    master_eq_air_boost_db=2.5,
    master_eq_mud_cut_db=-2.0,
    master_eq_sub_boost_db=1.0,
    limiter_ceiling=0.80,
    limiter_attack_ms=5.0,
    limiter_release_ms=20.0,
    dynaudnorm_maxgain=1.5,
)


# ── Preset lookup ───────────────────────────────────────────

PRESET_MAP: dict[str, SubgenreRenderPreset] = {
    "industrial_techno": INDUSTRIAL,
    "dub_techno": DUB_TECHNO,
    "hard_techno": HARD_TECHNO,
    "hypnotic_techno": HYPNOTIC,
    "peak_time_techno": PEAK_TIME,
    "driving_techno": DRIVING,
    "acid_techno": ACID,
    "raw_techno": INDUSTRIAL,        # близко к industrial
    "tribal_techno": DRIVING,        # близко к driving
    "detroit_techno": PEAK_TIME,     # близко к peak_time
    "deep_techno": DUB_TECHNO,       # близко к dub
    "minimal_techno": DUB_TECHNO,    # близко к dub
    "progressive_techno": PEAK_TIME, # close to peak_time
    "melodic_techno": HYPNOTIC,      # близко к hypnotic
}


def resolve_preset(mood: str | None) -> SubgenreRenderPreset | None:
    """Find the best preset for a mood label. Returns None if no match."""
    if not mood:
        return None
    return PRESET_MAP.get(mood.lower().replace(" ", "_"))


def resolve_preset_by_subgenre(subgenre: str | None) -> SubgenreRenderPreset | None:
    """Find preset by raw subgenre name (from stem filename genre tag)."""
    if not subgenre:
        return None
    key = subgenre.lower().strip()
    # Direct match
    if key in PRESET_MAP:
        return PRESET_MAP[key]
    # Try with _techno suffix
    if f"{key}_techno" in PRESET_MAP:
        return PRESET_MAP[f"{key}_techno"]
    return None
