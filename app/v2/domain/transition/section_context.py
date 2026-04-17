"""SectionContext — structural awareness for transition scoring.

A small frozen dataclass that tells the scorer which structural sections
the mix-out (from_t) and mix-in (to_t) windows belong to. When both
sides are percussion-only intro/outro/sustain regions, harmonic
compatibility becomes mostly irrelevant (Vande Veire & De Bie, JASMP
2018, Pioneer DJ blog) — the scorer suppresses the harmonic component
weight and applies a harmonic floor.

The dataclass is intentionally tiny: it has no logic beyond
``is_drum_only_pair``. The decision of *which* sections of a track to
mix on lives in ``app/services/mix_point_service.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.v2.shared.constants import SectionType

# Sections that are typically percussion-only in techno tracks.
# INTRO/OUTRO are drum-led DJ-friendly hooks; SUSTAIN/AMBIENT are
# textural beds without strong tonal centres.
_DRUM_ONLY_SECTIONS: frozenset[SectionType] = frozenset(
    {SectionType.INTRO, SectionType.OUTRO, SectionType.SUSTAIN, SectionType.AMBIENT}
)


@dataclass(frozen=True)
class SectionContext:
    """Section types for the mix-out and mix-in windows of a transition.

    ``from_section`` is what we are mixing OUT of (last bars of the
    outgoing track). ``to_section`` is what we are mixing INTO (first
    bars of the incoming track). Either may be ``None`` when section
    data is unavailable — in that case the context is treated as
    "no information", and scoring falls back to the full-track formula.
    """

    from_section: SectionType | None
    to_section: SectionType | None

    @property
    def is_drum_only_pair(self) -> bool:
        """True when both sides are in a percussion-only section.

        Used by ``score_harmonic`` to apply the relaxation floor and
        by ``TransitionScorer`` to swap to ``DRUM_ONLY_WEIGHT_OVERRIDE``.
        """
        if self.from_section is None or self.to_section is None:
            return False
        return self.from_section in _DRUM_ONLY_SECTIONS and self.to_section in _DRUM_ONLY_SECTIONS
