from dataclasses import FrozenInstanceError

import pytest

from app.domain.configuration.profile import TransitionProfile
from app.domain.configuration.resolver import ConfigResolver
from app.domain.configuration.schema import ParameterClass, ParameterDefinition, TransitionSchema


def schema() -> TransitionSchema:
    return TransitionSchema(
        (
            ParameterDefinition("tempo.max_ratio", "ratio", 0.5, 2.0, 1.06, ParameterClass.HARD),
            ParameterDefinition("energy.weight", "unitless", 0.0, 1.0, 0.5, ParameterClass.SOFT),
        )
    )


def test_resolver_obeys_global_to_render_precedence_and_tracks_provenance() -> None:
    resolved = ConfigResolver(schema()).resolve(
        global_defaults={"tempo.max_ratio": 1.04},
        genre_profile=TransitionProfile("techno", {"tempo.max_ratio": 1.05}),
        behavior_profile=TransitionProfile("smooth", {"energy.weight": 0.7}),
        set_overrides={"energy.weight": 0.8},
        transition_overrides={"tempo.max_ratio": 1.03},
        render_overrides={"energy.weight": 0.9},
    )
    assert resolved.values["tempo.max_ratio"] == 1.03
    assert resolved.values["energy.weight"] == 0.9
    assert resolved.provenance["energy.weight"].source == "render"


def test_resolver_rejects_unknown_fields_and_invalid_values() -> None:
    with pytest.raises(ValueError, match="unknown"):
        ConfigResolver(schema()).resolve(global_defaults={"nope": 1})
    with pytest.raises(ValueError, match=r"tempo\.max_ratio"):
        ConfigResolver(schema()).resolve(global_defaults={"tempo.max_ratio": 4.0})


def test_resolved_configuration_is_immutable_and_hash_is_deterministic() -> None:
    left = ConfigResolver(schema()).resolve(global_defaults={"tempo.max_ratio": 1.05})
    right = ConfigResolver(schema()).resolve(global_defaults={"tempo.max_ratio": 1.05})
    assert left.config_hash == right.config_hash
    with pytest.raises(FrozenInstanceError):
        left.values = {}  # type: ignore[misc]
