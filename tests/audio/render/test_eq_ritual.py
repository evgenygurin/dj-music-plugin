from app.domain.render.graph import build_filtergraph
from app.domain.render.models import RenderMode, RenderPlan, TrackSegment


def _segment(**kwargs):
    defaults = {
        "index": 0,
        "track_id": 1,
        "file_path": "t1.mp3",
        "tempo_ratio": 1.0,
        "trim_start_s": 0.0,
        "gain_db": 0.0,
        "body_bars": 64,
        "d_in_s": 0.0,
        "d_out_s": 0.0,
        "length_s": 64.0,
        "start_s": 0.0,
    }
    defaults.update(kwargs)
    return TrackSegment(**defaults)


class TestEQRitualFiltergraph:
    def test_three_band_split(self):
        plan = RenderPlan(
            mode=RenderMode.CLASSIC,
            target_bpm=130.0,
            xsplit_low_hz=250,
            xsplit_high_hz=4000,
            eq_phase_1_ratio=0.40,
            eq_phase_2_ratio=0.70,
            low_swap_beats=1.0,
            outro_fade_bars=12,
            limiter_ceiling=0.85,
            segments=[_segment()],
        )
        graph = build_filtergraph(plan)
        joined = ";".join(graph)

        assert "asplit=3" in joined
        assert "lowpass" in joined
        assert "highpass" in joined
        assert "amix=inputs=3" in joined

    def test_high_band_fades_first(self):
        """High band on second track fades in during phase 1 (first 40% of d_in)."""
        seg0 = _segment(index=0, d_out_s=30.0, length_s=94.0)
        seg1 = _segment(
            index=1,
            track_id=2,
            file_path="t2.mp3",
            d_in_s=30.0,
            d_out_s=0.0,
            length_s=94.0,
            start_s=64.0,
        )
        plan = RenderPlan(
            mode=RenderMode.CLASSIC,
            target_bpm=130.0,
            xsplit_low_hz=250,
            xsplit_high_hz=4000,
            eq_phase_1_ratio=0.40,
            eq_phase_2_ratio=0.70,
            low_swap_beats=1.0,
            outro_fade_bars=12,
            limiter_ceiling=0.85,
            segments=[seg0, seg1],
        )
        graph = build_filtergraph(plan)
        joined = ";".join(graph)
        # d_in=30, p1=0.40 → HIGH fade d=12.0s
        assert "d=12.000" in joined

    def test_mid_band_fades_second(self):
        """Mid band on second track starts at p1*d_in, duration (p2-p1)*d_in."""
        seg0 = _segment(index=0, d_out_s=30.0, length_s=94.0)
        seg1 = _segment(
            index=1,
            track_id=2,
            file_path="t2.mp3",
            d_in_s=30.0,
            d_out_s=0.0,
            length_s=94.0,
            start_s=64.0,
        )
        plan = RenderPlan(
            mode=RenderMode.CLASSIC,
            target_bpm=130.0,
            xsplit_low_hz=250,
            xsplit_high_hz=4000,
            eq_phase_1_ratio=0.40,
            eq_phase_2_ratio=0.70,
            low_swap_beats=1.0,
            outro_fade_bars=12,
            limiter_ceiling=0.85,
            segments=[seg0, seg1],
        )
        graph = build_filtergraph(plan)
        joined = ";".join(graph)
        # st=p1*d_in=12.0, d=(p2-p1)*d_in=9.0
        assert "st=12.000" in joined
        assert "d=9.000" in joined
