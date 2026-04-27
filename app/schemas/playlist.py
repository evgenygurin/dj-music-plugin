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
    # Audit iter 41 (T-39): ``source_app`` and ``platform_ids`` are
    # persisted on the model but were dropped on the floor. Knowing
    # which app (rekordbox / ym / serato) produced a playlist matters
    # for sync workflows; ``platform_ids`` is the JSON-encoded mapping
    # of provider playlist IDs needed for ``playlist_sync``.
    source_app: str | None = None
    platform_ids: str | None = None


class PlaylistFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id__eq: int | None = None
    id__in: list[int] | None = None
    # Audit iter 41: id range queries — same drift class as v1.2.36
    # SetFilter.
    id__gt: int | None = None
    id__gte: int | None = None
    id__lt: int | None = None
    id__lte: int | None = None
    name__eq: str | None = None
    name__icontains: str | None = None
    name__startswith: str | None = None
    source_of_truth__eq: str | None = None
    source_of_truth__in: list[str] | None = None
    parent_id__eq: int | None = None
    parent_id__in: list[int] | None = None
    parent_id__isnull: bool | None = None
    # Audit iter 41: lookups for the 2 newly-exposed columns.
    source_app__eq: str | None = None
    source_app__in: list[str] | None = None
    source_app__isnull: bool | None = None
    platform_ids__icontains: str | None = None
    platform_ids__isnull: bool | None = None


class PlaylistCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=500)
    parent_id: int | None = None
    source_of_truth: str = "local"
    # Audit iter 41: same 2 columns the View now exposes — also
    # write-able at create time so callers can stamp provenance
    # (e.g. ``source_app="rekordbox"``) without a follow-up update.
    source_app: str | None = Field(default=None, max_length=200)
    platform_ids: str | None = None


class PlaylistUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=500)
    parent_id: int | None = None
    source_of_truth: str | None = None
    # Audit iter 41: callers couldn't update provenance / platform IDs
    # after creation — important for re-attaching a freshly-imported
    # YM playlist to its bare-bones local twin.
    source_app: str | None = Field(default=None, max_length=200)
    platform_ids: str | None = None
