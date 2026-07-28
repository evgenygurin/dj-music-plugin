import json

import pytest

from app.handlers.render_diagnose import render_diagnose_handler


@pytest.mark.asyncio
async def test_diagnose_writes_report(tmp_path, monkeypatch):
    out = tmp_path / "MIX.mp3"
    out.write_bytes(b"fake")

    class _Rep:
        name = "MIX.mp3"
        duration_s = 120.0
        overall_rms_db = -11.0
        integrated_lufs = -12.0
        loudness_range_lu = 8.0
        overall_flatness = 0.15
        overall_onset_db = -18.0
        flagged = 1
        windows = [
            type(
                "W",
                (),
                {
                    "offset_s": 20.0,
                    "rms_db": -30.0,
                    "low_db": -40.0,
                    "stereo_corr": 0.95,
                    "stereo_width": 0.5,
                    "low_ratio": 0.3,
                    "centroid_hz": 2000.0,
                    "spectral_flatness": 0.2,
                    "rolloff_hz": 8000.0,
                    "spectral_contrast_mean": 10.0,
                    "onset_strength_db": -20.0,
                    "tags": ["DROPOUT -30dB"],
                },
            )()
        ]

    monkeypatch.setattr("app.handlers.render_diagnose.diagnose_mix", lambda p: _Rep())

    res = await render_diagnose_handler(
        ctx=None, job_id="v131-x", mix_path=str(out), workspace=str(tmp_path)
    )
    assert res.flagged == 1
    saved = json.loads((tmp_path / "diagnostics.json").read_text())
    assert saved["flagged"] == 1
