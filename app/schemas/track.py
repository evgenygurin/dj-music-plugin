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
    """Django-lookup filter schema for the ``track`` entity.

    Only columns present on the ``tracks`` table are listed. Audio-feature
    filters (BPM, key, LUFS, mood) live on the ``track_features`` entity —
    use ``entity_list(entity="track_features", ...)`` to filter by those.
    """

    model_config = ConfigDict(extra="forbid")

    id__in: list[int] | None = None
    id__eq: int | None = None
    title__icontains: str | None = None
    status__eq: int | None = None
    status__in: list[int] | None = None
    duration_ms__gte: int | None = None
    duration_ms__lte: int | None = None


class TrackCreate(BaseModel):
    """Create payload — dispatches to ``track_import`` handler.

    The handler fetches metadata from the named provider and inserts a
    Track + YandexMetadata + TrackExternalId row. Idempotent by
    (source, external_id): existing tracks are returned in ``skipped``.

    There is no "default-INSERT" path on this entity — track rows are
    always sourced from a provider — so only the import-relevant fields
    are accepted. Title / duration / status come straight from the
    provider response and cannot be overridden by the caller.
    """

    model_config = ConfigDict(extra="forbid")

    external_ids: list[str] = Field(
        ..., min_length=1, description="Provider track IDs (e.g. Yandex track ids)."
    )
    source: str = Field(
        default="yandex",
        description='Provider name from ProviderRegistry (e.g. "yandex").',
    )
    playlist_id: int | None = Field(
        default=None, description="Optional playlist to append imported tracks to."
    )


class TrackUpdate(BaseModel):
    """Partial update — only supplied fields are applied."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=500)
    sort_title: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    status: int | None = Field(default=None, ge=0, le=1)
