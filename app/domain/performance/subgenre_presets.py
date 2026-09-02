"""Subgenre-aware render presets — maps MoodClassifier profiles to RenderSettings overrides.

Each techno subgenre needs different transition lengths, EQ curves, and effects.
Industrial wants aggressive 8-bar bass swaps; dub techno wants 64-bar hypnotic fades.

Wire: MoodClassifier(SubgenreProfile) → SubgenreRenderPreset → RenderSettings overrides.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config.render import RenderSettings

# Load centralized subgenre constants (removes hardcoding)
_CONSTANTS_PATH = (
    pathlib.Path(__file__).resolve().parents[3] / "app" / "config" / "subgenre_constants.json"
)

try:
    with open(_CONSTANTS_PATH, encoding="utf-8") as _cf:
        _SUBGENRE_CONSTANTS = json.load(_cf)
except Exception:
    _SUBGENRE_CONSTANTS = {"presets": {}}


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


# ── Preset library (loaded from centralized constants) ─────────

# Backward-compatible loader: tries JSON constants first, falls back to inline definitions.
_PRESET_DATA = _SUBGENRE_CONSTANTS.get("presets", {})


def _load_preset(name: str) -> SubgenreRenderPreset:
    data = _PRESET_DATA.get(name)
    if data is None:
        raise KeyError(f"Preset '{name}' not found in subgenre_constants.json")
    return SubgenreRenderPreset(
        transition_bars=data.get("transition_bars", 48),
        body_bars=data.get("body_bars", 40),
        xsplit_low_hz=data.get("xsplit_low_hz", 250),
        xsplit_high_hz=data.get("xsplit_high_hz", 4000),
        eq_phase_1_ratio=data.get("eq_phase_1_ratio", 0.40),
        eq_phase_2_ratio=data.get("eq_phase_2_ratio", 0.70),
        low_swap_beats=data.get("low_swap_beats", 1.0),
        outro_fade_bars=data.get("outro_fade_bars", 12),
        hpf_cutoff_hz=data.get("hpf_cutoff_hz", 30.0),
        per_track_eq_mid_cut_db=data.get("per_track_eq_mid_cut_db", -1.0),
        per_track_eq_bright_boost_db=data.get("per_track_eq_bright_boost_db", 1.5),
        pre_comp_threshold_db=data.get("pre_comp_threshold_db", -16.0),
        pre_comp_ratio=data.get("pre_comp_ratio", 2.5),
        glue_comp_threshold_db=data.get("glue_comp_threshold_db", -13.0),
        glue_comp_ratio=data.get("glue_comp_ratio", 2.5),
        master_eq_air_boost_db=data.get("master_eq_air_boost_db", 1.5),
        master_eq_mud_cut_db=data.get("master_eq_mud_cut_db", -1.0),
        master_eq_sub_boost_db=data.get("master_eq_sub_boost_db", 0.5),
        limiter_ceiling=data.get("limiter_ceiling", 0.85),
        limiter_attack_ms=data.get("limiter_attack_ms", 10.0),
        limiter_release_ms=data.get("limiter_release_ms", 30.0),
        dynaudnorm_maxgain=data.get("dynaudnorm_maxgain", 2.5),
    )


INDUSTRIAL = _load_preset("industrial_techno")
DUB_TECHNO = _load_preset("dub_techno")
HARD_TECHNO = _load_preset("hard_techno")
HYPNOTIC = _load_preset("hypnotic_techno")
PEAK_TIME = _load_preset("peak_time_techno")
DRIVING = _load_preset("driving_techno")
ACID = _load_preset("acid_techno")
DEEP_HOUSE = _load_preset("deep_house")
TECH_HOUSE = _load_preset("tech_house")
PROGRESSIVE_HOUSE = _load_preset("progressive_house")
CLASSIC_HOUSE = _load_preset("classic_house")

# Aliases / close mappings (loaded from constants or inline fallback)
PRESET_MAP: dict[str, SubgenreRenderPreset] = {
    "industrial_techno": INDUSTRIAL,
    "dub_techno": DUB_TECHNO,
    "hard_techno": HARD_TECHNO,
    "hypnotic_techno": HYPNOTIC,
    "peak_time_techno": PEAK_TIME,
    "driving_techno": DRIVING,
    "acid_techno": ACID,
    "raw_techno": INDUSTRIAL,
    "tribal_techno": DRIVING,
    "detroit_techno": PEAK_TIME,
    "deep_techno": DUB_TECHNO,
    "minimal_techno": DUB_TECHNO,
    "progressive_techno": PEAK_TIME,
    "melodic_techno": HYPNOTIC,
    "deep_house": DEEP_HOUSE,
    "tech_house": TECH_HOUSE,
    "progressive_house": PROGRESSIVE_HOUSE,
    "classic_house": CLASSIC_HOUSE,
}

PRESET_MAP: dict[str, SubgenreRenderPreset] = {
    "industrial_techno": INDUSTRIAL,
    "dub_techno": DUB_TECHNO,
    "hard_techno": HARD_TECHNO,
    "hypnotic_techno": HYPNOTIC,
    "peak_time_techno": PEAK_TIME,
    "driving_techno": DRIVING,
    "acid_techno": ACID,
    "raw_techno": INDUSTRIAL,  # близко к industrial
    "tribal_techno": DRIVING,  # близко к driving
    "detroit_techno": PEAK_TIME,  # близко к peak_time
    "deep_techno": DUB_TECHNO,  # близко к dub
    "minimal_techno": DUB_TECHNO,  # близко к dub
    "progressive_techno": PEAK_TIME,  # close to peak_time
    "melodic_techno": HYPNOTIC,  # близко к hypnotic
    "deep_house": DEEP_HOUSE,
    "tech_house": TECH_HOUSE,
    "progressive_house": PROGRESSIVE_HOUSE,
    "classic_house": CLASSIC_HOUSE,
}


def resolve_preset(mood: str | None) -> SubgenreRenderPreset | None:
    """Find the best preset for a mood label. Returns None if no match."""
    if not mood:
        return None
    key = mood.strip().lower().replace(" ", "_")
    if key in PRESET_MAP:
        return PRESET_MAP[key]
    if f"{key}_house" in PRESET_MAP:
        return PRESET_MAP[f"{key}_house"]
    if f"{key}_techno" in PRESET_MAP:
        return PRESET_MAP[f"{key}_techno"]
    return None


def resolve_preset_by_subgenre(subgenre: str | None) -> SubgenreRenderPreset | None:
    """Find preset by raw subgenre name (from stem filename genre tag)."""
    if not subgenre:
        return None
    key = subgenre.strip().lower().replace(" ", "_")
    # Direct match
    if key in PRESET_MAP:
        return PRESET_MAP[key]
    # Try with _house suffix (house before techno per house-preset plan)
    if f"{key}_house" in PRESET_MAP:
        return PRESET_MAP[f"{key}_house"]
    # Try with _techno suffix
    if f"{key}_techno" in PRESET_MAP:
        return PRESET_MAP[f"{key}_techno"]
    return None
