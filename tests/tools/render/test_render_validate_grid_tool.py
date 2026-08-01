from types import SimpleNamespace

import pytest

from app.domain.render.models import TrackInput
from app.tools.render.render_validate_grid import render_validate_grid


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
        )
    ]


@pytest.mark.asyncio
async def test_validate_grid_passes_workspace_and_mix(tmp_path, monkeypatch):
    (tmp_path / "MIX.mp3").write_bytes(b"fake")

    captured = {}

    async def _fake_handler(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            version_id=1,
            job_id="v1",
            mix_path=str(tmp_path / "MIX.mp3"),
            target_bpm=130.0,
            tracks=[],
            plan_checks=[],
            max_dev_bpm=0.0,
            mean_abs_dev_bpm=0.0,
            ok_count=1,
            warn_count=0,
            fail_count=0,
            summary="grid OK.",
        )

    monkeypatch.setattr(
        "app.tools.render.render_validate_grid.render_validate_grid_handler", _fake_handler
    )
    monkeypatch.setattr(
        "app.tools.render.render_validate_grid.render_mix_path",
        lambda vid: str(tmp_path / "MIX.mp3"),
    )
    monkeypatch.setattr(
        "app.tools.render.render_validate_grid.render_workspace", lambda vid: str(tmp_path)
    )

    res = await render_validate_grid(version_id=1, uow=_StubUow(_inputs()), ctx=None)
    assert res.ok_count == 1
    assert captured["workspace"] == str(tmp_path)
    assert captured["mix_path"] == str(tmp_path / "MIX.mp3")
    assert captured["version_id"] == 1


@pytest.mark.asyncio
async def test_validate_grid_raises_without_mix(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.tools.render.render_validate_grid.render_mix_path",
        lambda vid: str(tmp_path / "missing.mp3"),
    )
    monkeypatch.setattr(
        "app.tools.render.render_validate_grid.render_workspace", lambda vid: str(tmp_path)
    )
    from app.shared.errors import ValidationError

    with pytest.raises(ValidationError):
        await render_validate_grid(version_id=1, uow=_StubUow(_inputs()), ctx=None)
