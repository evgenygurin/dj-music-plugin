from app.audio.render.runner import build_ffmpeg_cmd
from app.domain.render.models import RenderPlan, TrackSegment

BAR = 4 * (60.0 / 130.0)


def _plan():
    segs = [
        TrackSegment(
            index=0,
            track_id=1,
            file_path="/a.mp3",
            tempo_ratio=1.0,
            trim_start_s=0.4,
            gain_db=0.0,
            body_bars=24,
            d_in_s=0.0,
            d_out_s=0.0,
            length_s=24 * BAR,
            start_s=0.0,
        )
    ]
    return RenderPlan(
        target_bpm=130.0,
        xsplit_low_hz=250,
        xsplit_high_hz=4000,
        eq_phase_1_ratio=0.40,
        eq_phase_2_ratio=0.70,
        low_swap_beats=1.0,
        outro_fade_bars=12,
        limiter_ceiling=0.85,
        segments=segs,
    )


def test_cmd_has_one_input_per_segment_and_mapping():
    cmd = build_ffmpeg_cmd(_plan(), "/out.mp3")
    assert cmd[0] == "ffmpeg"
    assert cmd.count("-i") == 1
    assert "/a.mp3" in cmd
    assert "-filter_complex" in cmd
    assert cmd[-1] == "/out.mp3"
    assert "[mix]" in cmd  # -map [mix]
    assert "libmp3lame" in cmd
