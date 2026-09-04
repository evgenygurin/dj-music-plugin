"""Data-only transition profiles."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class TransitionProfile:
    """Declarative preset; it contains values, never executable policy."""

    name: str
    values: Mapping[str, float]
    parent: TransitionProfile | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("profile name must not be empty")
        if self.parent is self:
            raise ValueError("profile cannot inherit from itself")
        if self.parent is not None and self.parent.parent is not None:
            raise ValueError("profile inheritance is limited to one level")
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))

    def effective_values(self) -> dict[str, float]:
        values = {} if self.parent is None else self.parent.effective_values()
        values.update(self.values)
        return values
