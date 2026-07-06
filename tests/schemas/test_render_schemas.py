from app.schemas.render import (
    RenderBeatgridResult,
    RenderDiagnosticsResult,
    RenderMixdownResult,
)


def test_beatgrid_result_shape():
    r = RenderBeatgridResult(
        version_id=131,
        tracks=[
            {
                "track_id": 1,
                "trim_start_s": 0.4,
                "refined_trim_s": 0.42,
                "gain_db": 1.5,
                "phase_ms": 20.0,
                "flags": ["fixed"],
            },
        ],
    )
    assert r.version_id == 131 and r.tracks[0]["track_id"] == 1


def test_mixdown_result_shape():
    r = RenderMixdownResult(
        job_id="v131-abc",
        version_id=131,
        out_path="/x/MIX.mp3",
        duration_s=5400.0,
        true_peak_db=-1.4,
        level_jumps=0,
        near_silent_s=0,
    )
    assert r.out_path.endswith("MIX.mp3")


def test_diagnostics_result_shape():
    r = RenderDiagnosticsResult(
        job_id="v131-abc",
        overall_rms_db=-11.0,
        flagged=2,
        windows=[{"offset_s": 20.0, "tags": ["DROPOUT -30dB"]}],
    )
    assert r.flagged == 2
