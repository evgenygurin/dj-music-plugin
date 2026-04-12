"""Track domain schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from dj_music.schemas.base import BaseEntity, BaseFilter, BasePagination, BaseSort


class TrackSortField(StrEnum):
    ID = "id"
    BPM = "bpm"
    TITLE = "title"
    ENERGY = "energy"
    CREATED_AT = "created_at"


class Track(BaseEntity):
    """Full track entity."""

    title: str = ""
    sort_title: str = ""
    duration_ms: int = 0
    status: int = 0


class TrackBrief(BaseEntity):
    """Minimal track info for list views."""

    title: str = ""
    bpm: float | None = None
    key_code: int | None = None
    mood: str | None = None


class TrackFilter(BaseFilter, BaseSort, BasePagination):
    """Track filtering + sorting + pagination."""

    bpm_min: float | None = Field(None, ge=20, le=300)
    bpm_max: float | None = Field(None, ge=20, le=300)
    key_code: int | None = Field(None, ge=0, le=23)
    energy_min: float | None = Field(None, ge=0, le=1)
    energy_max: float | None = Field(None, ge=0, le=1)
    mood: str | None = None
    has_features: bool | None = None
    exclude_set_id: int | None = None
    sort_by: TrackSortField = TrackSortField.ID

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if self.bpm_min is not None and self.bpm_max is not None:
            if self.bpm_min > self.bpm_max:
                raise ValueError("bpm_min must be <= bpm_max")
        if self.energy_min is not None and self.energy_max is not None:
            if self.energy_min > self.energy_max:
                raise ValueError("energy_min must be <= energy_max")
        return self
