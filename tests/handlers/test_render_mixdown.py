import pytest

from app.domain.render.models import TrackInput
from app.handlers.render_mixdown import render_mixdown_handler
from app.shared.errors import ValidationError
from app.shared.render_jobs import RENDER_JOBS


class _StubUow:
    def __init__(self, inputs):
        class _SV:
            async def get_render_inputs(self, vid):
                return inputs

        self.set_versions = _SV()


@pytest.mark.asyncio
async def test_mixdown_builds_plan_runs_and_registers(tmp_path, monkeypatch):
    RENDER_JOBS.clear()
    inputs = [
        TrackInput(
            track_id=i,
            yandex_id=i,
            title=f"t{i}",
            bpm=130.0,
            key_code=1,
            mix_in_ms=0,
            integrated_lufs=-12.0,
            file_path=f"/x{i}.mp3",
        )
        for i in range(2)
    ]
    # pre-seed a beatgrid so no DSP runs
    import json

    (tmp_path / "beatgrid.json").write_text(
        json.dumps(
            [
                {
                    "track_id": 0,
                    "trim_start_s": 0.4,
                    "refined_trim_s": 0.4,
                    "gain_db": 0.0,
                    "phase_ms": 0.0,
                },
                {
                    "track_id": 1,
                    "trim_start_s": 0.4,
                    "refined_trim_s": 0.4,
                    "gain_db": 0.0,
                    "phase_ms": 0.0,
                },
            ]
        )
    )

    captured = {}

    def _fake_run(plan, out_path):
        captured["n"] = plan.n
        captured["out"] = out_path
        # simulate ffmpeg producing a file
        from pathlib import Path

        Path(out_path).write_bytes(b"ID3fake")

    monkeypatch.setattr("app.handlers.render_mixdown.run_render", _fake_run)
    monkeypatch.setattr(
        "app.handlers.render_mixdown.scan_mix",
        lambda p: type(
            "S",
            (),
            {"duration_s": 100.0, "true_peak_db": -1.4, "level_jumps": [], "near_silent_s": []},
        )(),
    )

    res = await render_mixdown_handler(
        ctx=None,
        uow=_StubUow(inputs),
        version_id=131,
        workspace=str(tmp_path),
        out_name="MIX.mp3",
        timestamp="20260706-000000",
    )
    assert captured["n"] == 2
    assert res.out_path.endswith("MIX.mp3")
    assert res.job_id == "v131-20260706-000000"
    assert RENDER_JOBS.get(res.job_id).done is True


@pytest.mark.parametrize(
    "out_name",
    [
        "../../../etc/cron.d/evil",
        "/etc/passwd",
        "sub/dir/mix.mp3",
        "..",
        "a\\b.mp3",
    ],
)
@pytest.mark.asyncio
async def test_mixdown_rejects_out_name_path_traversal(tmp_path, out_name):
    RENDER_JOBS.clear()
    inputs = [
        TrackInput(
            track_id=0,
            yandex_id=0,
            title="t0",
            bpm=130.0,
            key_code=1,
            mix_in_ms=0,
            integrated_lufs=-12.0,
            file_path="/x0.mp3",
        )
    ]
    with pytest.raises(ValidationError):
        await render_mixdown_handler(
            ctx=None,
            uow=_StubUow(inputs),
            version_id=131,
            workspace=str(tmp_path),
            out_name=out_name,
            timestamp="20260706-000000",
        )


@pytest.mark.asyncio
async def test_mixdown_clamps_body_bars_to_source_duration(tmp_path, monkeypatch):
    RENDER_JOBS.clear()
    inputs = [
        TrackInput(
            track_id=i,
            yandex_id=i,
            title=f"t{i}",
            bpm=140.0,
            key_code=1,
            mix_in_ms=0,
            integrated_lufs=-12.0,
            file_path=f"/x{i}.mp3",
            duration_ms=120_000,
        )
        for i in range(2)
    ]
    import json

    (tmp_path / "beatgrid.json").write_text(
        json.dumps(
            [
                {
                    "track_id": 0,
                    "trim_start_s": 0.0,
                    "refined_trim_s": 0.0,
                    "gain_db": 0.0,
                    "phase_ms": 0.0,
                },
                {
                    "track_id": 1,
                    "trim_start_s": 0.0,
                    "refined_trim_s": 0.0,
                    "gain_db": 0.0,
                    "phase_ms": 0.0,
                },
            ]
        )
    )

    captured = {}

    def _fake_run(plan, out_path):
        captured["body_bars"] = [seg.body_bars for seg in plan.segments]
        from pathlib import Path

        Path(out_path).write_bytes(b"ID3fake")

    monkeypatch.setattr("app.handlers.render_mixdown.run_render", _fake_run)
    monkeypatch.setattr(
        "app.handlers.render_mixdown.scan_mix",
        lambda p: type(
            "S",
            (),
            {"duration_s": 100.0, "true_peak_db": -1.4, "level_jumps": [], "near_silent_s": []},
        )(),
    )

    await render_mixdown_handler(
        ctx=None,
        uow=_StubUow(inputs),
        version_id=131,
        workspace=str(tmp_path),
        out_name="MIX.mp3",
        timestamp="20260706-000000",
    )

    assert captured["body_bars"][0] < 64
    assert captured["body_bars"][1] < 64


@pytest.mark.asyncio
async def test_mixdown_explicit_bar_overrides_take_precedence(tmp_path, monkeypatch):
    RENDER_JOBS.clear()
    inputs = [
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
        for i in range(2)
    ]
    import json

    (tmp_path / "beatgrid.json").write_text(
        json.dumps(
            [
                {
                    "track_id": 0,
                    "trim_start_s": 0.0,
                    "refined_trim_s": 0.0,
                    "gain_db": 0.0,
                    "phase_ms": 0.0,
                },
                {
                    "track_id": 1,
                    "trim_start_s": 0.0,
                    "refined_trim_s": 0.0,
                    "gain_db": 0.0,
                    "phase_ms": 0.0,
                },
            ]
        )
    )

    captured = {}

    def _fake_run(plan, out_path):
        captured["body_bars"] = [seg.body_bars for seg in plan.segments]
        captured["transition_lengths"] = [seg.d_out_s for seg in plan.segments[:-1]]
        from pathlib import Path

        Path(out_path).write_bytes(b"ID3fake")

    monkeypatch.setattr("app.handlers.render_mixdown.run_render", _fake_run)
    monkeypatch.setattr(
        "app.handlers.render_mixdown.scan_mix",
        lambda p: type(
            "S",
            (),
            {"duration_s": 100.0, "true_peak_db": -1.4, "level_jumps": [], "near_silent_s": []},
        )(),
    )

    await render_mixdown_handler(
        ctx=None,
        uow=_StubUow(inputs),
        version_id=131,
        workspace=str(tmp_path),
        out_name="MIX.mp3",
        timestamp="20260706-000000",
        body_bars=8,
        transition_bars=8,
    )

    assert captured["body_bars"] == [8, 8]
    assert captured["transition_lengths"] == [pytest.approx(8 * 4 * (60.0 / 130.0))]
