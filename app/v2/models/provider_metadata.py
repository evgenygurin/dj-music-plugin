"""External music platforms: provider registry + per-track metadata + raw responses.

Supports only the providers actually used today (Yandex). Spotify /
Beatport / SoundCloud legacy tables dropped in Phase 2 Alembic migration.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.v2.models.base import Base, TimestampMixin


class Provider(Base, TimestampMixin):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))


class YandexMetadata(Base, TimestampMixin):
    __tablename__ = "yandex_metadata"

    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
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
    track_id: Mapped[int | None] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    provider_code: Mapped[str] = mapped_column(String(50), index=True)
    endpoint: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    status_code: Mapped[int | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
