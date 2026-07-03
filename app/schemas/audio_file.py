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
    # Audit iter 39: 4 persisted columns were dropped on the floor by
    # the View — ``mime_type`` is even non-null on the model.
    # ``file_uri`` (file:// scheme), ``file_hash`` (sha256 dedup), and
    # ``source_app`` (which app produced the file) all matter for
    # storage audit / dedup workflows but were unprojectable.
    file_uri: str | None = None
    file_hash: str | None = None
    mime_type: str | None = None
    source_app: str | None = None


class BeatgridView(BaseModel):
    """One beatgrid row — payload of
    ``entity_get(audio_file, id, include_relations=["beatgrids"])``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    library_item_id: int
    bpm: float
    first_downbeat_ms: float | None = None
    grid_offset_ms: float | None = None
    confidence: float | None = None
    variable_tempo: bool = False
    canonical: bool = False


class AudioFileFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id__eq: int | None = None
    id__in: list[int] | None = None
    track_id__eq: int | None = None
    track_id__in: list[int] | None = None
    file_path__icontains: str | None = None
    # file_size: range queries to find oversized / undersized files
    # (audit iter 8).
    file_size__gte: int | None = None
    file_size__lte: int | None = None
    file_size__range: list[int] | None = None
    # bitrate: filter by audio quality (audit iter 13).
    bitrate__eq: int | None = None
    bitrate__gte: int | None = None
    bitrate__lte: int | None = None
    # sample_rate / channels: physical audio properties for filtering
    # studio-quality vs streaming-quality files (audit iter 19).
    sample_rate__eq: int | None = None
    sample_rate__in: list[int] | None = None
    channels__eq: int | None = None
    # Audit iter 39: lookups for the 4 newly-exposed columns.
    file_uri__icontains: str | None = None
    file_hash__eq: str | None = None
    file_hash__isnull: bool | None = None
    mime_type__eq: str | None = None
    mime_type__in: list[str] | None = None
    source_app__eq: str | None = None
    source_app__in: list[str] | None = None
    source_app__isnull: bool | None = None


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
    # Audio metadata - settable when running tag analysis on a file
    # already on disk (audit iter 27).
    bitrate: int | None = Field(default=None, ge=8, le=2_000)
    sample_rate: int | None = Field(default=None, ge=8_000, le=384_000)
    channels: int | None = Field(default=None, ge=1, le=8)
    # Audit iter 39: same 4 columns the View now exposes — also
    # write-able so callers can re-run dedup (file_hash) or relocate
    # to a new ``source_app`` without delete + recreate.
    file_uri: str | None = Field(default=None, max_length=1000)
    file_hash: str | None = Field(default=None, max_length=128)
    mime_type: str | None = Field(default=None, max_length=50)
    source_app: str | None = Field(default=None, max_length=100)
