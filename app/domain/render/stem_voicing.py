"""Stem voicing: single source of bleed-masking HPF and headroom trim.

Used by ``StemGraphBuilder`` so the HPF and per-stem gain staging live beside
``models.STEM_ORDER`` instead of being scattered across static methods in the
filtergraph module.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StemVoicing:
    hpf_hz: int | None
    gain_db: float


STEM_VOICING: dict[str, StemVoicing] = {
    "drums": StemVoicing(hpf_hz=None, gain_db=0.0),
    "bass": StemVoicing(hpf_hz=None, gain_db=0.0),
    "harmonic": StemVoicing(hpf_hz=80, gain_db=-2.0),
    "instrumental": StemVoicing(hpf_hz=120, gain_db=-7.0),
    "acappella": StemVoicing(hpf_hz=120, gain_db=-3.0),
}

_DEMUCS_STEM_VOICING: dict[str, StemVoicing] = {
    "vocals": StemVoicing(hpf_hz=120, gain_db=0.0),
    "other": StemVoicing(hpf_hz=80, gain_db=0.0),
}


def stem_voicing(stem: str) -> StemVoicing:
    return STEM_VOICING.get(stem) or _DEMUCS_STEM_VOICING[stem]
