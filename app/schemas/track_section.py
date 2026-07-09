"""TrackSection entity schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TrackSectionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    track_id: int
    section_type: int
    start_ms: int
    end_ms: int
    energy: float | None = None
    confidence: float | None = None
    lufs: float | None = None
    spectral_centroid: float | None = None
    stem_energy: dict | None = None


class TrackSectionFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    track_id__eq: int | None = None
    track_id__in: list[int] | None = None
    section_type__eq: int | None = None
    section_type__in: list[int] | None = None
    section_type__range: list[int] | None = None
    start_ms__gte: int | None = None
    start_ms__lte: int | None = None
    end_ms__gte: int | None = None
    end_ms__lte: int | None = None
    energy__gte: float | None = None
    energy__lte: float | None = None
    lufs__gte: float | None = None
    lufs__lte: float | None = None


class TrackSectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id: int
    section_type: int
    start_ms: int
    end_ms: int


class TrackSectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
