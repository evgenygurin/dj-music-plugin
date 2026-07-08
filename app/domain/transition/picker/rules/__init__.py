from __future__ import annotations

from app.domain.transition.api import PickerRule

from .ambient_or_cooldown import AmbientOrCooldownRule
from .default_drums import DefaultDrumsRule
from .drum_only_section import DrumOnlySectionRule
from .energy_drop_to_slam import EnergyDropToSlamRule
from .filter_sweep import FilterSweepRule
from .hard_reject_rescue import HardRejectRescueRule
from .harmonic_continuity import HarmonicContinuityRule
from .harmonic_sustain import HarmonicSustainRule
from .smooth_stem_blend import SmoothStemBlendRule
from .vocal_active import VocalActiveRule

DEFAULT_RULES: tuple[PickerRule, ...] = (
    HardRejectRescueRule(),
    DrumOnlySectionRule(),
    FilterSweepRule(),
    VocalActiveRule(),
    HarmonicSustainRule(),
    EnergyDropToSlamRule(),
    AmbientOrCooldownRule(),
    SmoothStemBlendRule(),
    HarmonicContinuityRule(),
    DefaultDrumsRule(),
)

__all__ = [
    "AmbientOrCooldownRule",
    "DEFAULT_RULES",
    "DefaultDrumsRule",
    "DrumOnlySectionRule",
    "EnergyDropToSlamRule",
    "FilterSweepRule",
    "HardRejectRescueRule",
    "HarmonicContinuityRule",
    "HarmonicSustainRule",
    "SmoothStemBlendRule",
    "VocalActiveRule",
]
