from app.application.engine.mode import EngineMode
from app.config import reset_settings_cache


def test_engine_settings_default_to_legacy(monkeypatch) -> None:
    monkeypatch.delenv("DJ_ENGINE", raising=False)
    monkeypatch.delenv("DJ_RENDERER", raising=False)
    reset_settings_cache()

    from app.config import get_settings

    assert get_settings().engine.engine == EngineMode.LEGACY
    assert get_settings().engine.renderer == "legacy"


def test_engine_settings_read_rollout_environment(monkeypatch) -> None:
    monkeypatch.setenv("DJ_ENGINE", "shadow")
    monkeypatch.setenv("DJ_RENDERER", "new")
    reset_settings_cache()

    from app.config import get_settings

    assert get_settings().engine.engine == EngineMode.SHADOW
    assert get_settings().engine.renderer == "new"

    monkeypatch.delenv("DJ_ENGINE", raising=False)
    monkeypatch.delenv("DJ_RENDERER", raising=False)
    reset_settings_cache()
