from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class TrackBrief(BaseModel):
    id: int
    title: str
    artist_names: list[str]
    bpm: float | None = None
    key_camelot: str | None = None
    duration_ms: int | None = None


class TrackStandard(TrackBrief):
    energy_lufs: float | None = None
    mood: str | None = None
    status: int = 0
    has_features: bool = False


class PlaylistSummary(BaseModel):
    id: int
    name: str
    track_count: int = 0
    source_of_truth: str = "local"


class SetSummary(BaseModel):
    id: int
    name: str
    track_count: int = 0
    template: str | None = None
    latest_score: float | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    total: int = 0
