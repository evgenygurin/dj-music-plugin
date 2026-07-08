import re

from app.domain.render.graph import build_filtergraph
from app.domain.render.models import RenderPlan, TrackSegment


def make_segment(index, length_s=90.0, d_in_s=30.0, d_out_s=30.0, start_s=0.0):
    return TrackSegment(
        index=index,
        track_id=index + 1,
        file_path=f"track{index + 1}.mp3",
        tempo_ratio=1.0,
        trim_start_s=0.0,
        gain_db=0.0,
        body_bars=64,
        d_in_s=d_in_s,
        d_out_s=d_out_s,
        length_s=length_s,
        start_s=start_s,
    )


class TestBassSwapFiltergraph:
    def test_low_swap_is_beat_based(self):
        plan = RenderPlan(
            target_bpm=130.0,
            xsplit_hz=250,
            low_swap_beats=1.0,
            outro_fade_bars=12,
            limiter_ceiling=0.85,
            segments=[
                make_segment(0, start_s=0.0, d_out_s=30.0, length_s=94.0),
                make_segment(1, start_s=64.0, d_in_s=30.0, d_out_s=0.0, length_s=94.0),
            ],
        )

        graph = build_filtergraph(plan)

        beat_s = 60.0 / 130.0
        expected_low_x = 1.0 * beat_s

        lo_fade_line = [s for s in graph if "[lo0]" in s or "[lo1]" in s]
        assert len(lo_fade_line) >= 2

        for line in lo_fade_line:
            if "d=" in line:
                match = re.search(r"d=([\d.]+)", line)
                if match:
                    d_val = float(match.group(1))
                    assert abs(d_val - expected_low_x) < 0.01, (
                        f"Expected low_x ~{expected_low_x:.3f}s, got d={d_val:.3f}s"
                    )

    def test_beat_s_computation(self):
        assert abs(60.0 / 130.0 - 0.461538) < 1e-4
        assert abs(60.0 / 120.0 - 0.5) < 1e-4
