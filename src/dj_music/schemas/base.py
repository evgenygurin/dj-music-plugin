"""Base classes for Entity-First architecture.

All domain data models inherit from these:
- BaseEntity — full domain entity (from_attributes=True for ORM mapping)
- BaseValueObject — immutable value object (frozen=True)
- BaseFilter — filtering params (all fields optional, extra forbidden)
- BaseSort — sorting params (sort_dir enum)
- BasePagination — cursor pagination params (limit + cursor)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from dj_music.core.constants import SortDir


class BaseEntity(BaseModel):
    """Base for all domain entities. Supports ORM → Pydantic mapping."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int = 0


class BaseValueObject(BaseModel):
    """Immutable value object. Structural equality."""

    model_config = ConfigDict(frozen=True)


class BasePagination(BaseModel):
    """Cursor-based pagination parameters."""

    limit: int = Field(20, ge=1, le=100, description="Items per page")
    cursor: str | None = Field(None, description="Opaque cursor for next page")


class BaseSort(BaseModel):
    """Sort direction. Subclasses add sort_by with domain-specific enum."""

    sort_dir: SortDir = SortDir.ASC


class BaseFilter(BaseModel):
    """Base filter — all fields optional, extra forbidden."""

    model_config = ConfigDict(extra="forbid")
