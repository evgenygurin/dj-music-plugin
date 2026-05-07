"""External music platforms: provider registry + per-track metadata + raw responses.

Synced with prod Supabase schema 2026-05-07. Audit revealed three drifts:

* ``providers`` carries a single ``name`` column — the prior ORM exposed
  ``code`` + ``display_name`` (never persisted to prod).
* ``yandex_metadata`` has a separate auto-increment ``id`` PK alongside
  ``track_id`` (UNIQUE) — the prior ORM treated ``track_id`` as the PK
  and would have failed inserts because the prod ``id`` column has no
  default.
* ``raw_provider_responses`` stores ``provider_id`` (FK) + ``raw_data``
  (text) + ``fetched_at`` — the prior ORM exposed
  ``provider_code`` / ``endpoint`` / ``body`` / ``status_code`` /
  ``error_message`` columns that do not exist in prod.

Spotify / Beatport / SoundCloud legacy tables remain drop-pending per
blueprint §13.2.
"""

from __future__ import annotations

import datetime
from datetime import date

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Provider(Base, TimestampMixin):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)


class YandexMetadata(Base, TimestampMixin):
    __tablename__ = "yandex_metadata"
    __table_args__ = (UniqueConstraint("track_id", name="uq_yandex_metadata_track_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    yandex_track_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    album_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    album_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    album_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    album_genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    album_year: Mapped[int | None] = mapped_column(nullable=True)
    label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    release_date: Mapped[date | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    cover_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    explicit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    extra: Mapped[str | None] = mapped_column(Text, nullable=True)


class RawProviderResponse(Base, TimestampMixin):
    __tablename__ = "raw_provider_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), index=True
    )
    raw_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
