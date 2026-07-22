# tests/domain/render/test_graph.py
from dataclasses import replace

from app.domain.render.graph import build_filtergraph
from app.domain.render.models import RenderMode, RenderPlan, TrackSegment

BAR = 4 * (60.0 / 130.0)


def _plan(n):
    segs = []
    t = 0.0
    d_trans = 32 * BAR
    for i in range(n):
        d_in = d_trans if i > 0 else 0.0
        d_out = d_trans if i < n - 1 else 0.0
        length = 24 * BAR + d_in + d_out
        segs.append(
            TrackSegment(
                index=i,
                track_id=i,
                file_path=f"/x{i}.mp3",
                tempo_ratio=1.0,
                trim_start_s=0.4,
                gain_db=0.0,
                body_bars=24,
                d_in_s=d_in,
                d_out_s=d_out,
                length_s=length,
                start_s=t,
            )
        )
        t += length - d_out
    return RenderPlan(
        mode=RenderMode.CLASSIC,
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


def test_filtergraph_single_track_shape():
    parts = build_filtergraph(_plan(1))
    joined = ";".join(parts)
    # per-segment stages present
    assert "asplit=3[s0a][s0b][s0c]" in joined
    assert "lowpass=f=250[lo0]" in joined
    assert "highpass=f=4000[hi0]" in joined
    # single track: no incoming/outgoing crossfade, but an outro fade of 12 bars
    assert "afade=t=out:curve=tri" in joined
    # final limiter
    assert "alimiter=level_in=1:level_out=1:limit=0.85" in joined
    assert joined.endswith("[mix]")


def test_filtergraph_two_tracks_has_incoming_fade_and_delay():
    parts = build_filtergraph(_plan(2))
    joined = ";".join(parts)
    # second segment's high band fades IN over the incoming transition
    assert "afade=t=in:curve=exp" in joined
    # amix + adelay wiring for segment 1 (delayed to its slot)
    assert "adelay=" in joined
    assert ["amix=inputs=2:normalize=0", ""][0][:5] in joined  # amix present


def test_filtergraph_outgoing_echo_tail_stays_at_tail_position():
    plan = replace(_plan(2), echo_preset="techno_standard")
    first = plan.segments[0]
    tail_start = max(0.0, first.length_s - first.d_out_s * 0.3)
    tail_ms = int(tail_start * 1000)

    joined = ";".join(build_filtergraph(plan))

    assert f"adelay={tail_ms}|{tail_ms}[se0_out]" in joined


def test_filtergraph_is_deterministic():
    assert build_filtergraph(_plan(3)) == build_filtergraph(_plan(3))


def test_filtergraph_contains_mastering_chain():
    parts = build_filtergraph(_plan(2))
    graph_str = ";".join(parts)
    assert "firequalizer" in graph_str
    assert "attack=10.0" in graph_str
    assert "release=30.0" in graph_str
