from app.application.engine.mode import EngineMode, EngineSelection


def test_default_mode_is_legacy_and_shadow_is_explicit() -> None:
    assert EngineSelection.from_values(None, None).engine is EngineMode.LEGACY
    assert EngineSelection.from_values("shadow", "new").engine is EngineMode.SHADOW
    assert EngineSelection.from_values("new", "new").renderer == "new"
