"""Base classes and protocols for domain entities.

Entities are pure dataclass domain objects: no SQLAlchemy, no Pydantic, no FastMCP.
They live in `app/entities/` and form the framework-agnostic Band 3 layer.

Identity-based equality (two entities are equal iff same type and same id),
NOT structural equality (so two Tracks with the same title are still distinct).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class HasId(Protocol):
    """Marker for entities with a stable identity."""

    id: int


@runtime_checkable
class HasTimestamps(Protocol):
    """Marker for entities tracked with creation / update timestamps."""

    created_at: datetime
    updated_at: datetime


@dataclass
class Entity:
    """Base entity with identity-based equality.

    Subclasses inherit identity semantics. Override `__eq__`/`__hash__`
    only if you need value semantics (then prefer a frozen dataclass VO).
    """

    id: int = 0

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash((type(self), self.id))


@dataclass(frozen=True, slots=True)
class ValueObject:
    """Marker base for frozen value objects.

    Subclasses get structural equality, hashability, and immutability for free
    via @dataclass(frozen=True, slots=True). Inherit from this when the object
    has no identity (e.g. Bpm(124.0), Lufs(-14.5), CamelotKey("8A")).
    """


__all__ = ["Entity", "HasId", "HasTimestamps", "ValueObject"]
