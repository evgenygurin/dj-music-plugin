"""Deterministic configuration resolution with provenance."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar

from .profile import TransitionProfile
from .provenance import Provenance
from .schema import TransitionSchema


@dataclass(frozen=True, slots=True)
class ResolvedTransitionConfig:
    values: Mapping[str, float]
    provenance: Mapping[str, Provenance]
    warnings: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))

    @property
    def config_hash(self) -> str:
        payload = {"values": dict(sorted(self.values.items()))}
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


EffectiveConfiguration = ResolvedTransitionConfig


class ConfigResolver:
    """Merge layers in the architecture-defined precedence order."""

    _LAYERS = (
        ("global", 1),
        ("genre", 2),
        ("behavior", 3),
        ("set", 4),
        ("transition", 5),
        ("render", 6),
    )

    def __init__(self, schema: TransitionSchema) -> None:
        self._schema = schema

    def resolve(
        self,
        *,
        global_defaults: Mapping[str, float] | None = None,
        genre_profile: TransitionProfile | None = None,
        behavior_profile: TransitionProfile | None = None,
        set_overrides: Mapping[str, float] | None = None,
        transition_overrides: Mapping[str, float] | None = None,
        render_overrides: Mapping[str, float] | None = None,
    ) -> ResolvedTransitionConfig:
        layers: dict[str, Mapping[str, float]] = {
            "global": global_defaults or {},
            "genre": genre_profile.effective_values() if genre_profile else {},
            "behavior": behavior_profile.effective_values() if behavior_profile else {},
            "set": set_overrides or {},
            "transition": transition_overrides or {},
            "render": render_overrides or {},
        }
        values = {name: definition.default for name, definition in self._schema.by_name.items()}
        provenance = {name: Provenance("default", 0, name) for name in self._schema.by_name}
        for source, priority in self._LAYERS:
            for name, value in layers[source].items():
                self._validate(name, value)
                values[name] = float(value)
                provenance[name] = Provenance(source, priority, name)
        return ResolvedTransitionConfig(values, provenance)

    def _validate(self, name: str, value: float) -> None:
        definition = self._schema.by_name.get(name)
        if definition is None:
            raise ValueError(f"unknown configuration field: {name}")
        if not definition.minimum <= float(value) <= definition.maximum:
            raise ValueError(
                f"{name} must be between {definition.minimum} and {definition.maximum}"
            )


class LegacyConfigAdapter:
    """Translate legacy setting names into the declarative schema namespace."""

    _TRANSITION_MAP: ClassVar[dict[str, str]] = {
        "hard_reject_bpm_diff": "tempo.max_bpm_difference",
        "hard_reject_energy_gap_lufs": "energy.max_gap_lufs",
    }

    def transition_values(self, legacy: Mapping[str, float]) -> dict[str, float]:
        return {
            target: float(legacy[source])
            for source, target in self._TRANSITION_MAP.items()
            if source in legacy
        }
