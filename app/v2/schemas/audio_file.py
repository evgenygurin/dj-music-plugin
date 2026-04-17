"""Audio file DTOs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AudioFileView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    track_id: int
    file_path: str
    file_size: int
    bitrate_kbps: int | None = None
    sample_rate: int | None = None
    channels: int | None = None


class AudioFileFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id__in: list[int] | None = None
    track_id__eq: int | None = None
    track_id__in: list[int] | None = None
    file_path__icontains: str | None = None


class AudioFileCreate(BaseModel):
    """Single or batch download-and-register.

    Either ``track_id`` (one) or ``track_ids`` (batch) must be set.
    ``source`` picks the provider (e.g. ``"yandex_music"``).
    """

    model_config = ConfigDict(extra="forbid")
    track_id: int | None = None
    track_ids: list[int] | None = None
    source: str = Field(..., min_length=1)


class AudioFileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_path: str | None = None
    file_size: int | None = Field(default=None, ge=0)
