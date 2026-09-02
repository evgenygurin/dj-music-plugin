"""Stem timbre: single source of bleed-masking HPF and headroom trim.

Used by StemTransitionPolicy engine so the HPF and per-stem gain staging live
beside models.STEM_ORDER instead of being scattered across static methods in
the filtergraph module.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StemTimbre:
    """Per-stem timbre parameters for bleed masking and headroom."""

    hpf_hz: int | None
    gain_db: float


STEM_TIMBRE: dict[str, StemTimbre] = {
    "vocals": StemTimbre(hpf_hz=120, gain_db=0.0),
    "drums": StemTimbre(hpf_hz=None, gain_db=0.0),
    "bass": StemTimbre(hpf_hz=None, gain_db=0.0),
    "harmonic": StemTimbre(hpf_hz=80, gain_db=-2.0),
    "percussion": StemTimbre(hpf_hz=120, gain_db=0.0),
}


def stem_timbre(stem: str) -> StemTimbre:
    """Get timbre parameters for a stem."""
    if stem not in STEM_TIMBRE:
        raise ValueError(f"Unknown stem: {stem}. Valid stems: {list(STEM_TIMBRE.keys())}")
    return STEM_TIMBRE[stem]


__all__ = ["STEM_TIMBRE", "StemTimbre", "stem_timbre"]
