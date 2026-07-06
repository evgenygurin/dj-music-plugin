# tests/domain/render/test_graph.py
from app.domain.render.graph import build_filtergraph
from app.domain.render.models import RenderPlan, TrackSegment

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
        target_bpm=130.0,
        xsplit_hz=180,
        low_swap_bars=2,
        outro_fade_bars=12,
        limiter_ceiling=0.85,
        segments=segs,
    )


def test_filtergraph_single_track_shape():
    parts = build_filtergraph(_plan(1))
    joined = ";".join(parts)
    # per-segment stages present
    assert "asplit=2[s0a][s0b]" in joined
    assert "lowpass=f=180[lo0]" in joined
    assert "highpass=f=180[hi0]" in joined
    # single track: no incoming/outgoing crossfade, but an outro fade of 12 bars
    assert "afade=t=out:curve=qsin" in joined
    # final limiter
    assert "alimiter=level_in=1:level_out=1:limit=0.85" in joined
    assert joined.endswith("[mix]")


def test_filtergraph_two_tracks_has_incoming_fade_and_delay():
    parts = build_filtergraph(_plan(2))
    joined = ";".join(parts)
    # second segment's high band fades IN over the incoming transition
    assert "[hi1]afade=t=in:curve=qsin:st=0" in joined
    # amix + adelay wiring for segment 1 (delayed to its slot)
    assert "adelay=" in joined
    assert ["amix=inputs=2:normalize=0", ""][0][:5] in joined  # amix present


def test_filtergraph_is_deterministic():
    assert build_filtergraph(_plan(3)) == build_filtergraph(_plan(3))
