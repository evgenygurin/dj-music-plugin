"""Ingestion models (Task 15).

2 tables: providers, raw_provider_responses.

Note: provider_track_ids was removed — duplicated by track_external_ids.
"""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ProviderModel(Base, TimestampMixin):
    """Supported data source (yandex_music, spotify, beatport, soundcloud)."""

    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


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
    fetched_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
