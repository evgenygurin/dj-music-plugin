"""register_default_entities wires 11 entities + custom handlers (Phase 3)."""

from __future__ import annotations

import pytest

from app.registry.defaults import register_default_entities
from app.registry.entity import EntityRegistry


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    EntityRegistry.clear()
    yield
    EntityRegistry.clear()


def test_registers_all_11_entities() -> None:
    register_default_entities()
    names = set(EntityRegistry.names())
    expected = {
        "track",
        "playlist",
        "set",
        "set_version",
        "audio_file",
        "track_features",
        "transition",
        "transition_history",
        "track_feedback",
        "track_affinity",
        "scoring_profile",
    }
    assert names == expected


def test_track_config_shape() -> None:
    register_default_entities()
    cfg = EntityRegistry.get("track")
    assert cfg.name == "track"
    assert cfg.repo_attr == "tracks"
    assert "list" in cfg.allowed_ops
    assert "id" in cfg.field_presets
    # ``default_preset="full"`` restores the pre-v1.0.13 entity_get/list
    # behaviour where the absence of explicit ``fields=`` returned the
    # whole view dump. The audit (2026-04-27) caught the regression to
    # ``"id"``-only stripping all entities to ``{id}`` by default.
    assert cfg.default_preset == "full"


def test_all_entities_default_preset_is_full() -> None:
    """Bug B regression: every registered entity must default to ``full``.

    The audit found ``default_preset="id"`` made every ``entity_get``
    response collapse to ``{id}`` only — useless for downstream tooling
    and a behavioural break against pre-v1.0.13 behaviour where the
    entire view shape was returned without a fields argument.
    """
    register_default_entities()
    misconfigured: list[tuple[str, str]] = []
    for name in EntityRegistry.names():
        cfg = EntityRegistry.get(name)
        if cfg.default_preset != "full":
            misconfigured.append((name, cfg.default_preset))
        assert "full" in cfg.field_presets, f"{name} missing 'full' preset"
    assert not misconfigured, (
        f"These entities still default to a stripped preset (Bug B regression): {misconfigured}"
    )


def test_track_has_import_handler() -> None:
    register_default_entities()
    cfg = EntityRegistry.get("track")
    assert cfg.create_handler is not None
    assert cfg.create_handler.__name__ == "track_import_handler"


def test_audio_file_has_download_handler() -> None:
    register_default_entities()
    cfg = EntityRegistry.get("audio_file")
    assert cfg.create_handler is not None
    assert cfg.create_handler.__name__ == "audio_file_download_handler"


def test_track_features_has_analyze_and_reanalyze_handlers() -> None:
    register_default_entities()
    cfg = EntityRegistry.get("track_features")
    assert cfg.create_handler is not None
    assert cfg.create_handler.__name__ == "track_features_analyze_handler"
    assert cfg.update_handler is not None
    assert cfg.update_handler.__name__ == "track_features_reanalyze_handler"


def test_transition_has_persist_handler() -> None:
    register_default_entities()
    cfg = EntityRegistry.get("transition")
    assert cfg.create_handler is not None
    assert cfg.create_handler.__name__ == "transition_persist_handler"


def test_set_version_has_build_handler() -> None:
    register_default_entities()
    cfg = EntityRegistry.get("set_version")
    assert cfg.create_handler is not None
    assert cfg.create_handler.__name__ == "set_version_build_handler"


def test_plain_entities_have_no_custom_handler() -> None:
    register_default_entities()
    for name in (
        "playlist",
        "set",
        "transition_history",
        "track_feedback",
        "track_affinity",
        "scoring_profile",
    ):
        cfg = EntityRegistry.get(name)
        assert cfg.create_handler is None, f"{name} should have no create handler"
        assert cfg.update_handler is None


def test_idempotent_register_raises_on_duplicate() -> None:
    register_default_entities()
    with pytest.raises(ValueError):
        register_default_entities()
