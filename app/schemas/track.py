"""Track entity DTOs: View / Filter / Create / Update."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TrackView(BaseModel):
    """Read projection — what clients see. Accepts ORM attr access."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    sort_title: str | None = None
    duration_ms: int | None = None
    status: int = 0
    primary_artist_name: str | None = None


class TrackFilter(BaseModel):
    """Django-lookup filter schema. Every field is optional."""

    model_config = ConfigDict(extra="forbid")

    id__in: list[int] | None = None
    id__eq: int | None = None
    title__icontains: str | None = None
    status__eq: int | None = None
    status__in: list[int] | None = None

    bpm__gte: float | None = None
    bpm__lte: float | None = None
    bpm__lt: float | None = None
    bpm__gt: float | None = None
    bpm__range: list[float] | None = None

    key_code__eq: int | None = None
    key_code__in: list[int] | None = None

    integrated_lufs__gte: float | None = None
    integrated_lufs__lte: float | None = None

    mood__eq: str | None = None
    mood__in: list[str] | None = None

    has_features__eq: bool | None = None


class TrackCreate(BaseModel):
    """Create payload (no custom handler → default INSERT; with handler → import from provider)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=500)
    sort_title: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    status: int = Field(default=0, ge=0, le=1)
    # Handler-driven import path:
    source: str | None = Field(default=None, description='e.g. "yandex_music"')
    provider_ids: list[str] | None = None


class TrackUpdate(BaseModel):
    """Partial update — only supplied fields are applied."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=500)
    sort_title: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    status: int | None = Field(default=None, ge=0, le=1)
