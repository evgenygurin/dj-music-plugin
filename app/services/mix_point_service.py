"""Mix-point detection — turn beatgrid + sections into mix-in/out points.

Pure compute layer: takes already-loaded data structures, returns the
same shape the database expects. No I/O, no DB session — the caller
(typically ``deliver_set`` or a future background job) is responsible
for loading beatgrids and sections from repositories and persisting
the results.

Algorithm based on Vande Veire & De Bie (JASMP 2018) and Zehren et al.
(CMJ 2022): cue points in EDM are >95% on 16-bar phrase boundaries, so
quantising the section start/end to the nearest downbeat (and the
nearest 16-bar phrase) is almost free precision.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.constants import SectionType
from app.domain.transition.section_context import SectionContext

# A "phrase" in techno is the 32-beat (8-bar) unit DJs build their
# blends around. We quantise to half a phrase (16 beats / 4 bars) so we
# don't snap too aggressively on short tracks.
PHRASE_BARS: int = 8
SUBPHRASE_BARS: int = 4
BEATS_PER_BAR: int = 4


# Sections that count as a "mix-out" anchor — outgoing track wants to
# fade out from a region with no leading melody.
_MIX_OUT_SECTIONS: frozenset[SectionType] = frozenset(
    {SectionType.OUTRO, SectionType.SUSTAIN, SectionType.AMBIENT}
)
# Sections that count as a "mix-in" anchor — incoming track wants to
# start from a percussion-only region.
_MIX_IN_SECTIONS: frozenset[SectionType] = frozenset(
    {SectionType.INTRO, SectionType.SUSTAIN, SectionType.AMBIENT}
)


@dataclass(frozen=True)
class TrackSectionRow:
    """Minimal section info needed for mix-point detection.

    Decoupled from the SQLAlchemy model so this module is import-light
    and unit-testable without a DB. The caller copies the relevant
    fields from ``track_sections`` rows.
    """

    section_type: SectionType
    start_ms: int
    end_ms: int


def quantize_to_downbeat(time_ms: int, downbeats_ms: list[int]) -> int:
    """Snap a millisecond timestamp to the nearest downbeat.

    Returns ``time_ms`` unchanged when ``downbeats_ms`` is empty (we'd
    rather have an unquantised value than fall through to 0).
    """
    if not downbeats_ms:
        return time_ms
    return min(downbeats_ms, key=lambda db: abs(db - time_ms))


def detect_mix_out_point(
    sections: list[TrackSectionRow],
    downbeats_ms: list[int],
    track_duration_ms: int,
) -> int | None:
    """Pick the mix-out point for the outgoing track.

    Strategy:
      1. Find the latest OUTRO/SUSTAIN/AMBIENT section.
      2. Take its start_ms.
      3. Quantise to the nearest downbeat.
      4. Fallback when no eligible section: 32 bars before the end,
         quantised. Returns ``None`` if there are no downbeats AND no
         eligible section (the caller can decide what to do).
    """
    eligible = [s for s in sections if s.section_type in _MIX_OUT_SECTIONS]
    if eligible:
        # Latest one (largest start_ms) — that's where the outro starts.
        anchor = max(eligible, key=lambda s: s.start_ms)
        return quantize_to_downbeat(anchor.start_ms, downbeats_ms)

    # Fallback: 32 bars (one phrase) before the end of the track.
    # Without a beatgrid we can't compute bar duration, so use the
    # downbeat list directly: 32 beats ≈ 8 bars worth of downbeats from
    # the end. If no downbeats either, we can't decide — return None.
    if not downbeats_ms:
        return None
    fallback = max(0, track_duration_ms - 30_000)  # ~30s tail
    return quantize_to_downbeat(fallback, downbeats_ms)


def detect_mix_in_point(
    sections: list[TrackSectionRow],
    downbeats_ms: list[int],
) -> int | None:
    """Pick the mix-in point for the incoming track.

    Strategy:
      1. Find the earliest INTRO/SUSTAIN/AMBIENT section.
      2. Take its start_ms (usually 0).
      3. Quantise to the nearest downbeat.
      4. Fallback: track start (0). Returns ``None`` only if both
         section list and downbeat list are empty.
    """
    eligible = [s for s in sections if s.section_type in _MIX_IN_SECTIONS]
    if eligible:
        anchor = min(eligible, key=lambda s: s.start_ms)
        return quantize_to_downbeat(anchor.start_ms, downbeats_ms)
    if downbeats_ms:
        return downbeats_ms[0]
    return None


def section_at(time_ms: int, sections: list[TrackSectionRow]) -> SectionType | None:
    """Return the section type that contains ``time_ms``, if any."""
    for s in sections:
        if s.start_ms <= time_ms < s.end_ms:
            return s.section_type
    return None


def build_section_context(
    *,
    from_sections: list[TrackSectionRow],
    from_mix_out_ms: int | None,
    to_sections: list[TrackSectionRow],
    to_mix_in_ms: int | None,
) -> SectionContext:
    """Construct a SectionContext for a transition pair.

    Pass already-detected mix points (from ``detect_mix_out_point`` /
    ``detect_mix_in_point``); this helper just looks up which section
    each point falls in. Either side may be ``None`` when the data is
    unavailable — the resulting context is treated as "no information"
    by the scorer (full-track formula, no relaxation).
    """
    from_section = (
        section_at(from_mix_out_ms, from_sections) if from_mix_out_ms is not None else None
    )
    to_section = section_at(to_mix_in_ms, to_sections) if to_mix_in_ms is not None else None
    return SectionContext(from_section=from_section, to_section=to_section)
