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
    data: dict[str, Any] = Field(default_factory=dict)


class ProviderSearchResult(BaseModel):
    provider: str
    query: str
    type: str
    total: int
    items: list[dict[str, Any]] = Field(default_factory=list)
