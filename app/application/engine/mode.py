"""Engine and renderer rollout modes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EngineMode(StrEnum):
    LEGACY = "legacy"
    SHADOW = "shadow"
    NEW = "new"


@dataclass(frozen=True, slots=True)
class EngineSelection:
    engine: EngineMode
    renderer: str

    @classmethod
    def from_values(cls, engine: str | None, renderer: str | None) -> EngineSelection:
        return cls(EngineMode(engine or EngineMode.LEGACY), renderer or "legacy")
