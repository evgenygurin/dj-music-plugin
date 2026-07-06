from app.tools.ui._fallback import RenderStudioFallback


def test_render_studio_fallback_shape():
    f = RenderStudioFallback(
        version_id=131,
        n_tracks=15,
        target_bpm=130.0,
        beatgrid=[{"track_id": 1, "phase_ms": 10.0, "gain_db": 1.5, "flags": ["fixed"]}],
        job={"job_id": "v131-x", "phase": "mixdown", "progress": 3, "total": 15},
        timeline=[{"index": 0, "title": "t1", "start_s": 0.0, "end_s": 100.0}],
        diagnostics=[{"offset_s": 20.0, "tags": ["DROPOUT -30dB"]}],
    )
    assert f.version_id == 131 and f.n_tracks == 15
    assert f.job["phase"] == "mixdown"


def test_render_studio_fallback_defaults():
    f = RenderStudioFallback(version_id=7)
    assert f.n_tracks == 0
    assert f.target_bpm is None
    assert f.beatgrid == [] and f.timeline == [] and f.diagnostics == []
    assert f.job is None
