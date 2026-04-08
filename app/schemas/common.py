"""Shared response envelopes and pagination primitives."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Cursor-based paginated response envelope.

    Used by every ``list_*`` tool to provide consistent ``structuredContent``.
    """

    items: list[T]
    next_cursor: str | None = None
    total: int = 0
