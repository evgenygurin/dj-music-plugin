"""Platform metadata schemas."""

from __future__ import annotations

from dj_music.schemas.base import BaseEntity


class YandexMetadata(BaseEntity):
    """Yandex Music enrichment data for a track."""

    track_id: int = 0
    yandex_track_id: str = ""
    album_id: str | None = None
    album_title: str | None = None
    album_type: str | None = None
    album_year: int | None = None
    label: str | None = None
    release_date: str | None = None
    duration_ms: int | None = None
    cover_uri: str | None = None
    explicit: bool | None = None
    # TODO: add spotify/beatport/soundcloud during Phase 4
