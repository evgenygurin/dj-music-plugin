# tests/domain/render/test_timeline.py
from app.domain.render.models import BeatgridEntry, TrackInput
from app.domain.render.timeline import build_render_plan, timeline_windows

# Two identical 130-BPM tracks, 24-bar bodies, 32-bar transitions.
BAR = 4 * (60.0 / 130.0)


def _inputs(n):
    return [
        TrackInput(
            track_id=i,
            yandex_id=i,
            title=f"t{i}",
            bpm=130.0,
            key_code=None,
            mix_in_ms=0,
            integrated_lufs=-12.0,
            file_path=f"/x{i}.mp3",
        )
        for i in range(n)
    ]


def _grid(n):
    return {
        i: BeatgridEntry(
            track_id=i, trim_start_s=0.0, refined_trim_s=0.0, gain_db=0.0, phase_ms=0.0
        )
        for i in range(n)
    }


def test_single_segment_no_transitions():
    plan = build_render_plan(
        _inputs(1),
        _grid(1),
        target_bpm=130.0,
        body_bars=24,
        transition_bars=32,
        xsplit_hz=180,
        low_swap_beats=1.0,
        outro_fade_bars=12,
        limiter_ceiling=0.85,
    )
    seg = plan.segments[0]
    assert seg.d_in_s == 0.0 and seg.d_out_s == 0.0
    assert round(seg.length_s, 4) == round(24 * BAR, 4)
    assert seg.start_s == 0.0


def test_two_segments_overlap():
    plan = build_render_plan(
        _inputs(2),
        _grid(2),
        target_bpm=130.0,
        body_bars=24,
        transition_bars=32,
        xsplit_hz=180,
        low_swap_beats=1.0,
        outro_fade_bars=12,
        limiter_ceiling=0.85,
    )
    s0, s1 = plan.segments
    # middle-of-nothing: first segment has no incoming, has outgoing 32 bars
    assert s0.d_in_s == 0.0
    assert round(s0.d_out_s, 4) == round(32 * BAR, 4)
    assert round(s0.length_s, 4) == round((24 + 32) * BAR, 4)
    # second starts (s0.length - d_out) earlier = at body-only offset
    assert round(s1.start_s, 4) == round(s0.length_s - s0.d_out_s, 4)
    assert round(s1.start_s, 4) == round(24 * BAR, 4)


def test_timeline_windows_reports_transitions():
    wins = timeline_windows(_inputs(3), target_bpm=130.0, body_bars=24, transition_bars=32)
    # 3 tracks => 2 transition windows
    assert len(wins.transitions) == 2
    assert wins.transitions[0].from_index == 0 and wins.transitions[0].to_index == 1
