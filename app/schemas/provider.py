"""Provider tool DTOs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ProviderResultView(BaseModel):
    provider: str
    entity: str
    id: str | None = None
    data: dict[str, Any]


class ProviderSearchItem(BaseModel):
    id: str
    title: str | None = None
    artists: list[str] = []
    extra: dict[str, Any] = {}


class ProviderSearchView(BaseModel):
    provider: str
    query: str
    type: Literal["tracks", "albums", "artists", "playlists", "all"]
    results: list[ProviderSearchItem]
    total: int | None = None
