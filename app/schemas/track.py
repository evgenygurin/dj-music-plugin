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

    Required: ``external_ids`` (list of provider track IDs as strings).
    Optional: ``source`` (provider name registered in ProviderRegistry,
    default ``"yandex"``), ``playlist_id`` (link imported tracks to a
    playlist), ``title`` / ``sort_title`` / ``duration_ms`` / ``status``
    (overrides — handler fills them from provider metadata otherwise).
    """

    model_config = ConfigDict(extra="forbid")

    # Handler-driven import path (primary surface):
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

    # Optional metadata overrides (handler pulls from provider when omitted):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    sort_title: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    status: int = Field(default=0, ge=0, le=1)


class TrackUpdate(BaseModel):
    """Partial update — only supplied fields are applied."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=500)
    sort_title: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    status: int | None = Field(default=None, ge=0, le=1)
