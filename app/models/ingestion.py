"""Ingestion models (Task 15).

3 tables: providers, provider_track_ids, raw_provider_responses.
"""

from __future__ import annotations

import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ProviderModel(Base, TimestampMixin):
    """Supported data source (yandex_music, spotify, beatport, soundcloud)."""

    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class ProviderTrackId(Base, TimestampMixin):
    """Mapping between local track and external provider track ID."""

    __tablename__ = "provider_track_ids"
    __table_args__ = (
        UniqueConstraint("track_id", "provider_id", name="uq_provider_track_ids_track_provider"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"),
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"),
    )
    provider_track_id: Mapped[str] = mapped_column(String(500))


class RawProviderResponse(Base, TimestampMixin):
    """Cached raw API response from a provider for a track."""

    __tablename__ = "raw_provider_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"),
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"),
    )
    raw_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
