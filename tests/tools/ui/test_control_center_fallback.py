from app.tools.ui._fallback import ControlCenterFallback


def test_control_center_fallback_shape():
    f = ControlCenterFallback(
        version_id=42,
        set_id=25,
        set_name="ga-all-fixed",
        quality_score=0.82,
        n_tracks=22,
        total_tracks=24005,
        analyzed_tracks=23817,
        coverage=0.992,
        tracks=[{"position": 0, "track_id": 977, "bpm": 130.0}],
        energy_arc=[{"position": 0, "lufs": -12.0}],
        bpm_histogram={"125-129": 12975},
        mood_distribution={"driving": 8333},
        beatgrid=[{"track_id": 1, "phase_ms": 10.0}],
        job={"job_id": "v42-x", "phase": "mixdown"},
        timeline=[{"index": 0, "title": "t1", "start_s": 0.0}],
        diagnostics=[{"offset_s": 20.0, "tags": ["DROPOUT"]}],
    )
    assert f.version_id == 42
    assert f.set_name == "ga-all-fixed"
    assert f.n_tracks == 22
    assert f.job["phase"] == "mixdown"


def test_control_center_fallback_defaults():
    f = ControlCenterFallback(version_id=1)
    assert f.n_tracks == 0
    assert f.tracks == []
    assert f.job is None
