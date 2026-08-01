import json

import numpy as np
import pytest
import soundfile as sf

pytest.importorskip("librosa")

from app.domain.render.models import TrackInput
from app.handlers.render_validate_grid import render_validate_grid_handler


class _StubUow:
    def __init__(self, inputs):
        class _SV:
            async def get_render_inputs(self, vid):
                return inputs

        self.set_versions = _SV()


def _inputs():
    return [
        TrackInput(
            track_id=1,
            yandex_id=9,
            title="a",
            bpm=130.0,
            key_code=1,
            mix_in_ms=0,
            integrated_lufs=-12.0,
            file_path="/a.mp3",
        ),
        TrackInput(
            track_id=2,
            yandex_id=8,
            title="b",
            bpm=130.0,
            key_code=1,
            mix_in_ms=0,
            integrated_lufs=-10.0,
            file_path="/b.mp3",
        ),
    ]


def _click_segment(bpm, sr=22050, dur=30.0):
    n = int(sr * dur)
    y = np.zeros(n, dtype="float32")
    beat = 60.0 / bpm
    t = 0.0
    while t < dur:
        i = int(t * sr)
        if i >= n:
            break
        k = min(int(0.04 * sr), n - i)
        env = np.hanning(k)
        y[i : i + k] += (0.9 * env * np.sin(2 * np.pi * 55 * np.arange(k) / sr)).astype("float32")
        t += beat
    return y


def _write_mix(path):
    sf.write(path, np.concatenate([_click_segment(130.0), _click_segment(131.5)]), 22050)


def _write_plan(ws):
    (ws / "render_plan.json").write_text(
        json.dumps(
            {
                "target_bpm": 130.0,
                "mode": "stem",
                "segments": [
                    {"track_id": 1, "start_s": 0.0, "end_s": 30.0},
                    {"track_id": 2, "start_s": 30.0, "end_s": 60.0},
                ],
            }
        )
    )


def _write_beatgrid(ws):
    (ws / "beatgrid.json").write_text(
        json.dumps(
            [
                {
                    "track_id": 1,
                    "trim_start_s": 0.4,
                    "refined_trim_s": 0.41,
                    "gain_db": 0.0,
                    "phase_ms": 10.0,
                    "bpm_measured": 145.0,
                },
                {
                    "track_id": 2,
                    "trim_start_s": 0.4,
                    "refined_trim_s": 0.41,
                    "gain_db": 0.0,
                    "phase_ms": 10.0,
                    "bpm_measured": 130.0,
                },
            ]
        )
    )


@pytest.mark.asyncio
async def test_handler_measures_bpm_and_writes_grid_check(tmp_path):
    ws = tmp_path
    _write_mix(str(ws / "MIX.mp3"))
    _write_plan(ws)
    _write_beatgrid(ws)

    res = await render_validate_grid_handler(
        ctx=None,
        uow=_StubUow(_inputs()),
        version_id=7,
        workspace=str(ws),
        mix_path=str(ws / "MIX.mp3"),
    )

    assert res.version_id == 7
    assert res.target_bpm == 130.0
    by_id = {t.track_id: t for t in res.tracks}
    assert by_id[1].status == "ok"
    assert abs(by_id[1].bpm_measured - 130.0) < 0.5
    assert by_id[2].status == "fail"
    assert abs(by_id[2].bpm_dev) > 1.0
    assert res.ok_count == 1
    assert res.fail_count == 1
    assert "FAIL" in res.summary

    pc = {p.track_id: p for p in res.plan_checks}
    assert pc[1].status == "fail"
    assert pc[1].bpm_measured == 145.0
    assert pc[2].status == "ok"

    saved = json.loads((ws / "grid_check.json").read_text())
    assert saved["version_id"] == 7
    assert len(saved["tracks"]) == 2


@pytest.mark.asyncio
async def test_handler_raises_when_mix_missing(tmp_path):
    with pytest.raises(Exception):
        await render_validate_grid_handler(
            ctx=None,
            uow=_StubUow(_inputs()),
            version_id=7,
            workspace=str(tmp_path),
            mix_path=str(tmp_path / "nope.mp3"),
        )
