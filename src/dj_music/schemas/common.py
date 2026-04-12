"""Common response types for the Entity-First architecture."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class CursorPage(BaseModel, Generic[T]):
    """Cursor-paginated response."""

    items: list[T]
    next_cursor: str | None = None
    total: int | None = None


# Alias used by services and tools migrated from app.schemas
PaginatedResponse = CursorPage
