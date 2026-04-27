"""Pydantic DTOs returned by provider_* tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProviderReadResult(BaseModel):
    provider: str
    entity: str
    data: dict[str, Any] = Field(default_factory=dict)


class ProviderWriteResult(BaseModel):
    provider: str
    entity: str
    operation: str
    # Some YM endpoints (e.g. playlist delete) return a bare string ``"ok"``
    # instead of a dict. Accept both shapes so the dispatcher doesn't crash
    # on response serialization.
    data: dict[str, Any] | str = Field(default_factory=dict)


class ProviderSearchResult(BaseModel):
    provider: str
    query: str
    type: str
    total: int
    items: list[dict[str, Any]] = Field(default_factory=list)
