"""DJ set DTOs — covers DjSet + DjSetVersion via nested create helpers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SetView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None = None
    target_duration_ms: int | None = None
    target_bpm_min: int | None = None
    target_bpm_max: int | None = None
    template_name: str | None = None
    source_playlist_id: int | None = None
    version_count: int | None = None


class SetFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id__in: list[int] | None = None
    name__icontains: str | None = None
    template_name__eq: str | None = None
    source_playlist_id__eq: int | None = None


class SetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    target_duration_ms: int | None = Field(default=None, ge=60_000, le=12 * 3600_000)
    target_bpm_min: int | None = Field(default=None, ge=60, le=250)
    target_bpm_max: int | None = Field(default=None, ge=60, le=250)
    template_name: str | None = None
    source_playlist_id: int | None = None
    algorithm: Literal["greedy", "ga"] | None = None


class SetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    description: str | None = None
    target_duration_ms: int | None = None
    template_name: str | None = None


class SetVersionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    set_id: int
    version_label: str
    quality_score: float | None = None
    generator_run_meta: dict[str, Any] | None = None


class SetVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    set_id: int
    version_label: str
    track_order: list[int]
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    generator_run_meta: dict[str, Any] | None = None
