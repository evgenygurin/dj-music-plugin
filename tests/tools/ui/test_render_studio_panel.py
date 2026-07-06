import json

import pytest

from app.domain.render.models import TrackInput


class _StubUow:
    def __init__(self, inputs):
        class _SV:
            async def get_render_inputs(self, vid):
                return inputs

        self.set_versions = _SV()


@pytest.mark.asyncio
async def test_gather_reads_workspace_and_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("DJ_DELIVERY_OUTPUT_DIR", str(tmp_path))
    from app.config import reset_settings_cache

    reset_settings_cache()

    from app.tools.ui.render_studio import gather_render_studio

    ws = tmp_path / "render" / "v131"
    ws.mkdir(parents=True)
    (ws / "beatgrid.json").write_text(
        json.dumps(
            [
                {
                    "track_id": 1,
                    "trim_start_s": 0.4,
                    "refined_trim_s": 0.4,
                    "gain_db": 1.5,
                    "phase_ms": 45.0,
                    "flags": ["fixed"],
                },
            ]
        )
    )
    (ws / "diagnostics.json").write_text(
        json.dumps(
            {
                "windows": [
                    {
                        "offset_s": 20.0,
                        "rms_db": -30.0,
                        "low_db": -40.0,
                        "tags": ["DROPOUT -30dB"],
                    },
                    {"offset_s": 40.0, "rms_db": -12.0, "low_db": -20.0, "tags": []},
                ]
            }
        )
    )
    from app.shared.render_jobs import RENDER_JOBS

    RENDER_JOBS.clear()
    RENDER_JOBS.start(job_id="v131-x", version_id=131, phase="mixdown")

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
        )
    ]
    data = await gather_render_studio(_StubUow(inputs), version_id=131, job_id="v131-x")
    assert data["version_id"] == 131
    assert data["n_tracks"] == 1
    assert data["target_bpm"] == 130.0
    assert data["beatgrid"][0]["flags"] == ["fixed"]
    assert data["job"]["phase"] == "mixdown"
    assert data["timeline"][0]["index"] == 0
    assert data["timeline"][0]["title"] == "t1"
    # only windows carrying tags survive
    assert len(data["diagnostics"]) == 1
    assert data["diagnostics"][0]["tags"] == ["DROPOUT -30dB"]

    RENDER_JOBS.clear()


@pytest.mark.asyncio
async def test_gather_missing_workspace_and_job(tmp_path, monkeypatch):
    monkeypatch.setenv("DJ_DELIVERY_OUTPUT_DIR", str(tmp_path))
    from app.config import reset_settings_cache

    reset_settings_cache()

    from app.tools.ui.render_studio import gather_render_studio

    inputs = [
        TrackInput(
            track_id=2,
            yandex_id=None,
            title="t2",
            bpm=128.0,
            key_code=None,
            mix_in_ms=0,
            integrated_lufs=None,
            file_path="/b.mp3",
        )
    ]
    data = await gather_render_studio(_StubUow(inputs), version_id=999, job_id=None)
    assert data["beatgrid"] == []
    assert data["diagnostics"] == []
    assert data["job"] is None
    assert data["n_tracks"] == 1


@pytest.mark.asyncio
async def test_panel_tool_returns_a_component_fragment(tmp_path, monkeypatch):
    """render_studio_panel is the CallTool target for SetState("panel", RESULT).

    It must return a bare component (not a PrefabApp) so the Prefab client
    writes the fragment straight into the Slot("panel") state key.
    """
    monkeypatch.setenv("DJ_DELIVERY_OUTPUT_DIR", str(tmp_path))
    from app.config import reset_settings_cache

    reset_settings_cache()

    from app.tools.ui.render_studio import render_studio_panel

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
        )
    ]
    fragment = await render_studio_panel(version_id=131, uow=_StubUow(inputs))
    # Not a PrefabApp: it has no top-level `view`/`state` split, just a
    # component with a `.to_json()` that serializes the visible card titles.
    assert not hasattr(fragment, "view")
    payload = json.dumps(fragment.to_json())
    assert "Job status" in payload
    assert "Timeline" in payload
    assert "t1" in payload
