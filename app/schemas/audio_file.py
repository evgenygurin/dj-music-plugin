"""Audio file DTOs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AudioFileView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    track_id: int
    file_path: str
    file_size: int
    bitrate: int | None = None
    sample_rate: int | None = None
    channels: int | None = None


class AudioFileFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id__eq: int | None = None
    id__in: list[int] | None = None
    track_id__eq: int | None = None
    track_id__in: list[int] | None = None
    file_path__icontains: str | None = None


class AudioFileCreate(BaseModel):
    """Single or batch download-and-register.

    Either ``track_id`` (one) or ``track_ids`` (batch) must be set.
    ``source`` picks the provider registered in ``ProviderRegistry``
    (e.g. ``"yandex"`` — NOT ``"yandex_music"``).
    """

    model_config = ConfigDict(extra="forbid")
    track_id: int | None = Field(
        default=None, description="Single track id (mutually exclusive with track_ids)."
    )
    track_ids: list[int] | None = Field(default=None, description="Batch of track ids.")
    source: str = Field(
        default="yandex",
        min_length=1,
        description='Provider name from ProviderRegistry, e.g. "yandex".',
    )


class AudioFileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_path: str | None = None
    file_size: int | None = Field(default=None, ge=0)
