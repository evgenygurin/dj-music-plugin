"""CuePointDetector — auto-detect DJ hot cues from track structure analysis.

Uses the existing StructureAnalyzer output (track_sections table) to place
hot cues at musically meaningful positions. Mimics what Rekordbox/MixedInKey
auto-analysis does.

Standard 8-cue layout for techno:
  A — First downbeat (grid anchor)
  B — Build-up start (where energy begins rising)
  C — Drop / Peak (maximum energy)
  D — Breakdown / ambient section
  E — Second drop (if present)
  F — Outro start (safe mix-out point)
  G — 16 bars before drop (pre-drop cue for quick transitions)
  H — 32 bars from end (last safe mix-in point for next DJ)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class CueType(IntEnum):
    GRID = 0       # beatgrid anchor
    BUILD = 1      # build-up start
    DROP = 2       # peak energy
    BREAKDOWN = 3  # breakdown / ambient
    OUTRO = 4      # safe mix-out
    LOOP_IN = 5    # loop start (8-16 bars of stable energy)
    LOOP_OUT = 6   # loop end
    PRE_DROP = 7   # 16 bars before drop (quick mix cue)


@dataclass(frozen=True, slots=True)
class CuePoint:
    """One hot cue / memory point for DJ software."""
    index: int          # 0-7 (A-H)
    cue_type: CueType
    position_ms: int
    label: str
    color: str = ""     # hex for Rekordbox (e.g. "#FF0000")


@dataclass
class CuePointSet:
    """Complete 8-cue layout for a track."""
    track_id: int
    cues: list[CuePoint] = field(default_factory=list)
    bpm: float = 0.0
    first_downbeat_ms: float = 0.0

    def rekordbox_xml(self) -> str:
        """Generate Rekordbox XML <POSITION_MARK> entries."""
        lines = []
        for cue in self.cues:
            name = f"{cue.label} ({cue.cue_type.name})"
            lines.append(
                f'      <POSITION_MARK Name="{name}" '
                f'Type="0" Start="{cue.position_ms / 1000.0:.6f}" '
                f'Num="-1" Red="{self._hex_to_r(cue.color)}" '
                f'Green="{self._hex_to_g(cue.color)}" '
                f'Blue="{self._hex_to_b(cue.color)}"/>'
            )
        return "\n".join(lines)

    @staticmethod
    def _hex_to_r(hex_color: str) -> int:
        if len(hex_color) >= 7:
            return int(hex_color[1:3], 16)
        return 255

    @staticmethod
    def _hex_to_g(hex_color: str) -> int:
        if len(hex_color) >= 5:
            return int(hex_color[3:5], 16)
        return 0

    @staticmethod
    def _hex_to_b(hex_color: str) -> int:
        if len(hex_color) >= 7:
            return int(hex_color[5:7], 16)
        return 0


# Section type constants from app/models/track_features.py TrackSection
# (0-11 as defined in the check constraint ck_section_type_range)
SECTION_NAMES: dict[int, str] = {
    0: "intro",
    1: "build",
    2: "drop",
    3: "breakdown",
    4: "peak",
    5: "outro",
    6: "valley",
    7: "sustain",
    8: "attack",
    9: "ambient",
    10: "bridge",
    11: "buildup",
}


def detect_cues(
    sections: list[dict],
    bpm: float,
    first_downbeat_ms: float = 0.0,
    duration_ms: int = 0,
) -> CuePointSet:
    """Analyze track sections and place 8 hot cues.

    sections: list of dicts with keys {section_type, start_ms, end_ms, energy, confidence}
        as returned by StructureAnalyzer / track_sections table.
    """
    track_id = sections[0].get("track_id", 0) if sections else 0
    cues: list[CuePoint] = []

    # Sort sections by start time
    sorted_secs = sorted(sections, key=lambda s: s.get("start_ms", 0))

    # ── Cue A: First downbeat ──
    cues.append(CuePoint(
        index=0, cue_type=CueType.GRID,
        position_ms=int(first_downbeat_ms),
        label="A: Grid", color="#FF0000",
    ))

    # ── Cue B: Build-up start (section_type=1 or energy rising steeply) ──
    builds = [s for s in sorted_secs if s.get("section_type") in (1, 8)]
    if builds:
        cues.append(CuePoint(
            index=1, cue_type=CueType.BUILD,
            position_ms=int(builds[0]["start_ms"]),
            label="B: Build", color="#00FF00",
        ))
    else:
        # Fallback: 32 bars before first drop
        bar_ms = 240000.0 / bpm if bpm > 0 else 2000.0
        drops = [s for s in sorted_secs if s.get("section_type") in (2, 4)]
        if drops:
            pos = max(0, drops[0]["start_ms"] - 32 * bar_ms)
            cues.append(CuePoint(
                index=1, cue_type=CueType.BUILD,
                position_ms=int(pos),
                label="B: Build (est)", color="#00FF00",
            ))

    # ── Cue C: First drop / Peak (section_type=2 or 4) ──
    drops = [s for s in sorted_secs if s.get("section_type") in (2, 4)]
    if drops:
        best = max(drops, key=lambda s: s.get("energy", 0) or 0)
        cues.append(CuePoint(
            index=2, cue_type=CueType.DROP,
            position_ms=int(best["start_ms"]),
            label="C: Drop", color="#0000FF",
        ))

    # ── Cue D: Breakdown (section_type=3, 6, or 9) ──
    breakdowns = [s for s in sorted_secs if s.get("section_type") in (3, 6, 9)]
    if breakdowns:
        cues.append(CuePoint(
            index=3, cue_type=CueType.BREAKDOWN,
            position_ms=int(breakdowns[0]["start_ms"]),
            label="D: Break", color="#FFFF00",
        ))

    # ── Cue E: Second drop ──
    if len(drops) >= 2:
        cues.append(CuePoint(
            index=4, cue_type=CueType.DROP,
            position_ms=int(drops[1]["start_ms"]),
            label="E: Drop 2", color="#FF00FF",
        ))

    # ── Cue F: Outro (section_type=5) ──
    outros = [s for s in sorted_secs if s.get("section_type") == 5]
    if outros:
        cues.append(CuePoint(
            index=5, cue_type=CueType.OUTRO,
            position_ms=int(outros[0]["start_ms"]),
            label="F: Outro", color="#FF8800",
        ))
    elif duration_ms > 0:
        cues.append(CuePoint(
            index=5, cue_type=CueType.OUTRO,
            position_ms=max(0, duration_ms - 32000),
            label="F: Outro (est)", color="#FF8800",
        ))

    # ── Cue G: Pre-drop (16 bars before drop) ──
    if drops:
        bar_ms = 240000.0 / bpm if bpm > 0 else 2000.0
        pos = max(0, drops[0]["start_ms"] - 16 * bar_ms)
        cues.append(CuePoint(
            index=6, cue_type=CueType.PRE_DROP,
            position_ms=int(pos),
            label="G: Pre-drop", color="#00FFFF",
        ))

    # ── Cue H: 32 bars from end ──
    if duration_ms > 0 and bpm > 0:
        bar_ms = 240000.0 / bpm
        pos = max(0, duration_ms - 32 * bar_ms)
        cues.append(CuePoint(
            index=7, cue_type=CueType.LOOP_IN,
            position_ms=int(pos),
            label="H: 32b from end", color="#FFFFFF",
        ))

    return CuePointSet(track_id=track_id, cues=cues, bpm=bpm,
                       first_downbeat_ms=first_downbeat_ms)


@dataclass
class TransitionCueWindow:
    """Optimal transition window between two tracks based on their structure."""

    from_track_id: int
    to_track_id: int
    mix_out_start_ms: int   # when to start mixing OUT of track A
    mix_out_end_ms: int     # when track A should be fully out
    mix_in_start_ms: int    # when to start mixing IN track B
    mix_in_end_ms: int      # when track B should be fully in
    recommendation: str     # human-readable advice


def find_transition_window(
    from_sections: list[dict],
    to_sections: list[dict],
    bpm: float,
) -> TransitionCueWindow:
    """Find the best transition window between two tracks.

    Strategy:
    - Mix out of track A during its outro section (or last 32 bars)
    - Mix in track B from its intro section (or first 16-32 bars)
    - Align so the energy handoff feels natural
    """
    bar_ms = 240000.0 / bpm if bpm > 0 else 2000.0
    transition_bars = 32  # default techno transition length
    transition_ms = transition_bars * bar_ms

    # Find outro of track A
    from_sorted = sorted(from_sections, key=lambda s: s.get("start_ms", 0))
    outros_a = [s for s in from_sorted if s.get("section_type") == 5]
    outro_start = outros_a[0]["start_ms"] if outros_a else 0

    # Find intro of track B
    to_sorted = sorted(to_sections, key=lambda s: s.get("start_ms", 0))
    intros_b = [s for s in to_sorted if s.get("section_type") == 0]
    intro_end = intros_b[0]["end_ms"] if intros_b else 32000

    mix_out_start = outro_start if outro_start > 0 else 0
    mix_out_end = mix_out_start + transition_ms
    mix_in_start = 0
    mix_in_end = intro_end

    # If track A has no outro detected, mix out from last 32 bars
    if outro_start == 0 and from_sections:
        last = from_sections[-1]
        track_end = last.get("end_ms", 0)
        mix_out_start = max(0, track_end - transition_ms)
        mix_out_end = track_end

    recommendation = (
        f"Mix OUT of track A at {mix_out_start/1000:.1f}s ({mix_out_start/(bar_ms*4):.0f} bars from end), "
        f"IN track B at {mix_in_start/1000:.1f}s (intro). "
        f"Transition: {transition_bars} bars ({transition_ms/1000:.0f}s)."
    )

    return TransitionCueWindow(
        from_track_id=from_sections[0].get("track_id", 0) if from_sections else 0,
        to_track_id=to_sections[0].get("track_id", 0) if to_sections else 0,
        mix_out_start_ms=int(mix_out_start),
        mix_out_end_ms=int(mix_out_end),
        mix_in_start_ms=int(mix_in_start),
        mix_in_end_ms=int(mix_in_end),
        recommendation=recommendation,
    )
