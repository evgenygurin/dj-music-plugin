"""Shared Pydantic DTOs used across tools + resources."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EntityRef(BaseModel):
    """Opaque reference to a registered entity."""

    model_config = ConfigDict(frozen=True)

    entity: str
    id: int


class EntityListView(BaseModel):
    """Generic paginated list response for ``entity_list``."""

    items: list[dict[str, Any]]
    next_cursor: str | None = None
    total: int | None = None
    preset: str | None = None
    fields: list[str] = Field(default_factory=list)

    @property
    def has_more(self) -> bool:
        return self.next_cursor is not None


class EntityAggregateView(BaseModel):
    """Generic aggregate response."""

    operation: Literal["count", "distinct", "histogram", "min_max", "sum", "avg", "group_by"]
    value: float | int | None = None
    distinct_values: list[Any] | None = None
    min: float | int | None = None
    max: float | int | None = None
    histogram: list[dict[str, Any]] | None = None
    groups: dict[str, int] | None = None
