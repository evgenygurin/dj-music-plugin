"""Playlist DTOs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PlaylistView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    parent_id: int | None = None
    source_of_truth: str = "local"
    item_count: int | None = None


class PlaylistFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id__in: list[int] | None = None
    name__icontains: str | None = None
    source_of_truth__eq: str | None = None
    parent_id__eq: int | None = None
    parent_id__isnull: bool | None = None


class PlaylistCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=500)
    parent_id: int | None = None
    source_of_truth: str = "local"


class PlaylistUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=500)
    parent_id: int | None = None
    source_of_truth: str | None = None
