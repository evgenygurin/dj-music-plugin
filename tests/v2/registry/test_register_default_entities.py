"""Registering default entities populates the registry with 11 configs."""

from __future__ import annotations

import pytest

from app.v2.registry.defaults import register_default_entities
from app.v2.registry.entity import EntityRegistry


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    EntityRegistry.clear()


def test_register_all() -> None:
    register_default_entities()
    names = EntityRegistry.names()
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
    assert set(names) == expected


def test_track_config_shape() -> None:
    register_default_entities()
    cfg = EntityRegistry.get("track")
    assert cfg.name == "track"
    assert cfg.repo_attr == "tracks"
    assert "list" in cfg.allowed_ops
    assert "id" in cfg.field_presets
    assert cfg.default_preset == "id"
    assert cfg.create_handler is None


def test_idempotent_register_raises_on_duplicate() -> None:
    register_default_entities()
    with pytest.raises(ValueError):
        register_default_entities()
