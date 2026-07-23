import json

import pytest

from app.domain.render.models import TrackInput
from app.handlers.render_beatgrid import render_beatgrid_handler


class _StubUow:
    def __init__(self, inputs):
        class _SV:
            async def get_render_inputs(self, vid):
                return inputs

        self.set_versions = _SV()


@pytest.mark.asyncio
async def test_beatgrid_writes_file_and_result(tmp_path, monkeypatch):
    inputs = [
        TrackInput(
            track_id=1,
            yandex_id=9,
            title="t1",
            bpm=130.0,
            key_code=1,
            mix_in_ms=0,
            integrated_lufs=-12.0,
            file_path="/a.mp3",
        ),
        TrackInput(
            track_id=2,
            yandex_id=8,
            title="t2",
            bpm=130.0,
            key_code=1,
            mix_in_ms=0,
            integrated_lufs=-10.0,
            file_path="/b.mp3",
        ),
    ]
    # stub the DSP so no librosa/ffmpeg needed
    monkeypatch.setattr(
        "app.handlers._orchestrator.beatgrid_provider.detect_kick_trim",
        lambda f, start_s, bpm: 0.4,
    )
    monkeypatch.setattr(
        "app.handlers._orchestrator.beatgrid_provider.refine_phase",
        lambda f, base_trim_s, bpm: (10.0, 0.41),
    )

    res = await render_beatgrid_handler(
        ctx=None,
        uow=_StubUow(inputs),
        version_id=131,
        workspace=str(tmp_path),
        refresh=True,
    )
    assert res.version_id == 131
    assert len(res.tracks) == 2
    grid = json.loads((tmp_path / "beatgrid.json").read_text())
    assert grid[0]["refined_trim_s"] == 0.41
    # median LUFS of (-12,-10) is -11 -> track1 gain +1, track2 gain -1
    g = {r["track_id"]: r["gain_db"] for r in res.tracks}
    assert g[1] == 1.0 and g[2] == -1.0


@pytest.mark.asyncio
async def test_beatgrid_clamps_phase_and_trim_for_late_kick_entries(tmp_path, monkeypatch):
    inputs = [
        TrackInput(
            track_id=1,
            yandex_id=9,
            title="t1",
            bpm=130.0,
            key_code=1,
            mix_in_ms=0,
            integrated_lufs=-18.0,
            file_path="/a.mp3",
            duration_ms=180000,
        )
    ]
    monkeypatch.setattr(
        "app.handlers._orchestrator.beatgrid_provider.detect_kick_trim",
        lambda f, start_s, bpm: 12.3,
    )
    monkeypatch.setattr(
        "app.handlers._orchestrator.beatgrid_provider.refine_phase",
        lambda f, base_trim_s, bpm: (229.3, 12.5293),
    )

    res = await render_beatgrid_handler(
        ctx=None,
        uow=_StubUow(inputs),
        version_id=131,
        workspace=str(tmp_path),
        refresh=True,
    )
    row = res.tracks[0]
    assert row["trim_start_s"] <= 8.0
    assert abs(row["phase_ms"]) <= 120.0
    assert row["refined_trim_s"] <= row["trim_start_s"] + 0.12
