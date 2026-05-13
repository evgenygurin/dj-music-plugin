"""SectionContext — structural awareness for transition scoring.

A small frozen dataclass that tells the scorer which structural sections
the mix-out (from_t) and mix-in (to_t) windows belong to. The
``section_pair_class`` property classifies the pair into one of five
typology buckets (DRUM_ONLY / DROP_TO_DROP / BREAKDOWN_OUT / BUILDUP_IN
/ GENERIC); the scorer applies per-class weight overlays so that an
outro→intro pair is not penalised for harmonic mismatch (Vande Veire &
De Bie, JASMP 2018, Pioneer DJ blog), a drop→drop pair weights drums
and bass more aggressively, etc.

The dataclass remains intentionally small: it has no IO and no
scoring logic, only typology. The decision of *which* sections of a
track to mix on lives elsewhere; here we just label the resulting pair.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property

from app.shared.constants import SectionType


class SectionPairClass(StrEnum):
    """5-bucket typology for an (out-section, in-section) pair.

    Used by ``TransitionScorer`` to select a multiplicative overlay on
    the base component weights, and by the picker to bias preset
    selection. Order in the file is roughly "specific → generic":

    * ``DRUM_ONLY`` — both sides percussion-only (INTRO / OUTRO /
      SUSTAIN / AMBIENT). Harmonic mismatch tolerable; phrase /
      structure compatibility critical.
    * ``DROP_TO_DROP`` — both sides at peak intensity (DROP / PEAK).
      Drums + bass tight; harmonic clash hideable under intensity.
    * ``BREAKDOWN_OUT`` — A in melodic breakdown / valley, B in
      drum-led intro / rise. Harmonic preservation matters.
    * ``BUILDUP_IN`` — A rising (BUILD / RISE), B landing the drop
      (DROP / PEAK). Phrase + structure dominate; harmonic secondary.
    * ``GENERIC`` — fallback when neither side is informative or the
      pair doesn't match any specific class.
    """

    DRUM_ONLY = "drum_only"
    DROP_TO_DROP = "drop_to_drop"
    BREAKDOWN_OUT = "breakdown_out"
    BUILDUP_IN = "buildup_in"
    GENERIC = "generic"


# Sections that are typically percussion-only in techno tracks.
# INTRO/OUTRO are drum-led DJ-friendly hooks; SUSTAIN/AMBIENT are
# textural beds without strong tonal centres.
_DRUM_ONLY_SECTIONS: frozenset[SectionType] = frozenset(
    {SectionType.INTRO, SectionType.OUTRO, SectionType.SUSTAIN, SectionType.AMBIENT}
)

# Sections at peak intensity. Used by DROP_TO_DROP classification.
_DROP_SECTIONS: frozenset[SectionType] = frozenset({SectionType.DROP, SectionType.PEAK})

# Sections that "lead away from a drop": melodic breakdowns and valleys.
_BREAKDOWN_OUT_FROM: frozenset[SectionType] = frozenset(
    {SectionType.BREAKDOWN, SectionType.VALLEY}
)
_BREAKDOWN_OUT_TO: frozenset[SectionType] = frozenset({SectionType.INTRO, SectionType.RISE})

# Sections that "build into a drop": ramps and rises.
_BUILDUP_FROM: frozenset[SectionType] = frozenset({SectionType.BUILD, SectionType.RISE})
_BUILDUP_TO: frozenset[SectionType] = frozenset({SectionType.DROP, SectionType.PEAK})


@dataclass(frozen=True)
class SectionContext:
    """Section types for the mix-out and mix-in windows of a transition.

    ``from_section`` is what we are mixing OUT of (last bars of the
    outgoing track). ``to_section`` is what we are mixing INTO (first
    bars of the incoming track). Either may be ``None`` when section
    data is unavailable — in that case the pair is classified as
    ``GENERIC`` and the scorer falls back to the base-weight formula
    with no overlay.
    """

    from_section: SectionType | None
    to_section: SectionType | None

    @cached_property
    def section_pair_class(self) -> SectionPairClass:
        """Classify the (out, in) section pair into one of five buckets.

        Order of checks matches priority: more specific patterns first,
        ``GENERIC`` as fallback. Both ``from_section`` and
        ``to_section`` must be non-None for any non-GENERIC class —
        with missing section data we can't meaningfully classify.
        """
        if self.from_section is None or self.to_section is None:
            return SectionPairClass.GENERIC
        if self.from_section in _DRUM_ONLY_SECTIONS and self.to_section in _DRUM_ONLY_SECTIONS:
            return SectionPairClass.DRUM_ONLY
        if self.from_section in _DROP_SECTIONS and self.to_section in _DROP_SECTIONS:
            return SectionPairClass.DROP_TO_DROP
        if self.from_section in _BREAKDOWN_OUT_FROM and self.to_section in _BREAKDOWN_OUT_TO:
            return SectionPairClass.BREAKDOWN_OUT
        if self.from_section in _BUILDUP_FROM and self.to_section in _BUILDUP_TO:
            return SectionPairClass.BUILDUP_IN
        return SectionPairClass.GENERIC

    @property
    def is_drum_only_pair(self) -> bool:
        """Legacy alias — preserved for ``picker.py`` callers.

        Equivalent to ``section_pair_class == SectionPairClass.DRUM_ONLY``.
        New code should consume ``section_pair_class`` directly to
        access the full 5-class typology.
        """
        return self.section_pair_class == SectionPairClass.DRUM_ONLY
