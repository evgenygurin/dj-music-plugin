import json

import pytest

from app.handlers.render_diagnose import render_diagnose_handler


@pytest.mark.asyncio
async def test_diagnose_writes_report(tmp_path, monkeypatch):
    out = tmp_path / "MIX.mp3"
    out.write_bytes(b"fake")

    class _Rep:
        name = "MIX.mp3"
        overall_rms_db = -11.0
        flagged = 1
        windows = [
            type(
                "W",
                (),
                {"offset_s": 20.0, "rms_db": -30.0, "low_db": -40.0, "tags": ["DROPOUT -30dB"]},
            )()
        ]

    monkeypatch.setattr("app.handlers.render_diagnose.diagnose_mix", lambda p: _Rep())

    res = await render_diagnose_handler(
        ctx=None, job_id="v131-x", mix_path=str(out), workspace=str(tmp_path)
    )
    assert res.flagged == 1
    saved = json.loads((tmp_path / "diagnostics.json").read_text())
    assert saved["flagged"] == 1
