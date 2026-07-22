from __future__ import annotations

from app.domain.performance.cue_points import CueType, detect_cues, find_transition_window
from app.shared.constants import SectionType


def test_detect_cues_uses_shared_section_type_values() -> None:
    sections = [
        {"track_id": 7, "section_type": SectionType.INTRO, "start_ms": 0, "end_ms": 32000},
        {"track_id": 7, "section_type": SectionType.BUILD, "start_ms": 32000, "end_ms": 64000},
        {
            "track_id": 7,
            "section_type": SectionType.DROP,
            "start_ms": 64000,
            "end_ms": 96000,
            "energy": 0.9,
        },
        {
            "track_id": 7,
            "section_type": SectionType.BREAKDOWN,
            "start_ms": 96000,
            "end_ms": 128000,
        },
        {"track_id": 7, "section_type": SectionType.OUTRO, "start_ms": 180000, "end_ms": 220000},
    ]

    cue_set = detect_cues(sections, bpm=120.0, duration_ms=220000)
    by_type = {cue.cue_type: cue for cue in cue_set.cues}

    assert by_type[CueType.BUILD].position_ms == 32000
    assert by_type[CueType.DROP].position_ms == 64000
    assert by_type[CueType.BREAKDOWN].position_ms == 96000
    assert by_type[CueType.OUTRO].position_ms == 180000


def test_find_transition_window_honors_preferred_bars() -> None:
    from_sections = [
        {"track_id": 1, "section_type": SectionType.OUTRO, "start_ms": 120000, "end_ms": 180000}
    ]
    to_sections = [
        {"track_id": 2, "section_type": SectionType.INTRO, "start_ms": 0, "end_ms": 32000}
    ]

    win = find_transition_window(from_sections, to_sections, bpm=120.0, preferred_bars=16)

    assert win.mix_out_start_ms == 120000
    assert win.mix_out_end_ms == 152000
    assert "Transition: 16 bars" in win.recommendation
