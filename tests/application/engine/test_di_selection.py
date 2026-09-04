from app.application.engine.mode import EngineMode
from app.config import reset_settings_cache
from app.config.engine import EngineSettings


def test_engine_settings_selection_exposes_rollout_modes(monkeypatch) -> None:
    monkeypatch.setenv("DJ_ENGINE", "shadow")
    monkeypatch.setenv("DJ_RENDERER", "new")

    settings = EngineSettings()
    selection = settings.selection()

    assert selection.engine is EngineMode.SHADOW
    assert selection.renderer == "new"


def test_engine_settings_selection_defaults_to_legacy(monkeypatch) -> None:
    monkeypatch.delenv("DJ_ENGINE", raising=False)
    monkeypatch.delenv("DJ_RENDERER", raising=False)
    reset_settings_cache()

    selection = EngineSettings().selection()

    assert selection.engine is EngineMode.LEGACY
    assert selection.renderer == "legacy"
