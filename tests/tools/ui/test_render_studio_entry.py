import pytest

from app.domain.render.models import TrackInput


class _StubUow:
    def __init__(self, inputs):
        class _SV:
            async def get_render_inputs(self, vid):
                return inputs

        self.set_versions = _SV()


class _NoUiCtx:
    def client_supports_extension(self, _ext):
        return False


class _UiCtx:
    def client_supports_extension(self, _ext):
        return True


def _inputs():
    return [
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


@pytest.mark.asyncio
async def test_entry_returns_fallback_when_no_prefab(tmp_path, monkeypatch):
    monkeypatch.setenv("DJ_DELIVERY_OUTPUT_DIR", str(tmp_path))
    from app.config import reset_settings_cache

    reset_settings_cache()

    from app.tools.ui._fallback import RenderStudioFallback
    from app.tools.ui.render_studio import ui_render_studio

    res = await ui_render_studio(version_id=131, uow=_StubUow(_inputs()), ctx=_NoUiCtx())
    assert isinstance(res, RenderStudioFallback)
    assert res.version_id == 131 and res.n_tracks == 1


@pytest.mark.asyncio
async def test_entry_returns_prefab_app_when_ui(tmp_path, monkeypatch):
    monkeypatch.setenv("DJ_DELIVERY_OUTPUT_DIR", str(tmp_path))
    from app.config import reset_settings_cache

    reset_settings_cache()

    from prefab_ui.app import PrefabApp

    from app.tools.ui.render_studio import ui_render_studio

    res = await ui_render_studio(version_id=131, uow=_StubUow(_inputs()), ctx=_UiCtx())
    assert isinstance(res, PrefabApp)
