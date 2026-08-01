import json
from types import SimpleNamespace

import pytest

from app.domain.render.models import TrackInput
from app.tools.render.render_diagnose import render_diagnose


class _StubUow:
    def __init__(self, inputs):
        class _TF:
            async def get_scoring_features_batch(self, ids):
                return {}

        class _SV:
            async def get_render_inputs(self, vid):
                return inputs

        self.track_features = _TF()
        self.set_versions = _SV()


def _inputs(n=2):
    return [
        TrackInput(
            track_id=i,
            yandex_id=i,
            title=f"t{i}",
            bpm=130.0,
            key_code=1,
            mix_in_ms=0,
            integrated_lufs=-12.0,
            file_path=f"/x{i}.mp3",
            duration_ms=600_000,
        )
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_diagnose_uses_persisted_render_plan(tmp_path, monkeypatch):
    (tmp_path / "MIX.mp3").write_bytes(b"fake")
    (tmp_path / "render_plan.json").write_text(
        json.dumps(
            {
                "target_bpm": 130.0,
                "mode": "stem",
                "subgenre": "peak_time_techno",
                "segments": [
                    {"track_id": 0, "start_s": 0.0, "end_s": 100.0},
                    {"track_id": 1, "start_s": 60.0, "end_s": 200.0},
                ],
            }
        )
    )

    captured = {}

    class _Rep:
        name = "MIX.mp3"
        duration_s = 200.0
        overall_rms_db = -12.0
        integrated_lufs = -13.0
        loudness_range_lu = 8.0
        overall_flatness = 0.2
        overall_onset_db = -18.0
        flagged = 0
        windows = []

    async def _fake_handler(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            job_id="v1",
            overall_rms_db=-12.0,
            integrated_lufs=-13.0,
            loudness_range_lu=8.0,
            overall_flatness=0.2,
            overall_onset_db=-18.0,
            flagged=0,
            windows=[],
            flow=None,
        )

    monkeypatch.setattr("app.tools.render.render_diagnose.render_diagnose_handler", _fake_handler)
    monkeypatch.setattr(
        "app.tools.render.render_diagnose.render_mix_path",
        lambda vid: str(tmp_path / "MIX.mp3"),
    )
    monkeypatch.setattr(
        "app.tools.render.render_diagnose.render_workspace", lambda vid: str(tmp_path)
    )

    res = await render_diagnose(version_id=1, uow=_StubUow(_inputs()), ctx=None)
    assert res.flagged == 0
    segs = captured["version_context"]["segments"]
    assert segs == [(0, 0.0, 100.0), (1, 60.0, 200.0)]
    assert captured["version_context"]["subgenre"] == "peak_time_techno"


@pytest.mark.asyncio
async def test_diagnose_falls_back_to_defaults_without_plan(tmp_path, monkeypatch):
    (tmp_path / "MIX.mp3").write_bytes(b"fake")

    captured = {}

    async def _fake_handler(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            job_id="v1",
            overall_rms_db=-12.0,
            integrated_lufs=-13.0,
            loudness_range_lu=8.0,
            overall_flatness=0.2,
            overall_onset_db=-18.0,
            flagged=0,
            windows=[],
            flow=None,
        )

    monkeypatch.setattr("app.tools.render.render_diagnose.render_diagnose_handler", _fake_handler)
    monkeypatch.setattr(
        "app.tools.render.render_diagnose.render_mix_path",
        lambda vid: str(tmp_path / "MIX.mp3"),
    )
    monkeypatch.setattr(
        "app.tools.render.render_diagnose.render_workspace", lambda vid: str(tmp_path)
    )

    res = await render_diagnose(version_id=1, uow=_StubUow(_inputs()), ctx=None)
    assert res.flagged == 0
    segs = captured["version_context"]["segments"]
    assert len(segs) == 2
    assert all(s[1] >= 0 and s[2] > s[1] for s in segs)
