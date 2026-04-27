"""Audio file DTOs."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    Exactly one of ``track_id`` (single) or ``track_ids`` (batch) must be
    set; the model validator below rejects both-set / both-None / empty
    batch at validation time so callers see a clean Pydantic error
    instead of a mid-handler ``ValueError``.

    ``source`` picks the provider registered in ``ProviderRegistry``
    (e.g. ``"yandex"`` — NOT the legacy DB seed name ``"yandex_music"``).
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
    target_dir: str | None = Field(
        default=None,
        description="Override download directory (defaults to /tmp/dj_audio).",
    )
    skip_existing: bool = Field(
        default=True, description="Skip tracks that already have a registered audio file."
    )
    number_files: bool = Field(
        default=True, description="Prefix filenames with NN. for sortable listings."
    )

    @model_validator(mode="after")
    def _exactly_one_target(self) -> Self:
        has_single = self.track_id is not None
        has_batch = self.track_ids is not None
        if has_single == has_batch:
            raise ValueError("AudioFileCreate requires exactly one of 'track_id' or 'track_ids'")
        if has_batch and not self.track_ids:
            raise ValueError("'track_ids' must contain at least one id")
        return self


class AudioFileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_path: str | None = None
    file_size: int | None = Field(default=None, ge=0)
