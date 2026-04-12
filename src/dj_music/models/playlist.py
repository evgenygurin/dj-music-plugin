"""Playlist models (Task 12).

2 tables: dj_playlists, dj_playlist_items.
"""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dj_music.core.utils.time import utc_now
from dj_music.models.base import Base, TimestampMixin


class Playlist(Base, TimestampMixin):
    """An ordered collection of tracks, optionally hierarchical."""

    __tablename__ = "dj_playlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("dj_playlists.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_app: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_of_truth: Mapped[str] = mapped_column(
        String(100), default="local", server_default="local"
    )
    platform_ids: Mapped[str | None] = mapped_column(Text, nullable=True)

    parent: Mapped[Playlist | None] = relationship(
        back_populates="children", remote_side="Playlist.id"
    )
    children: Mapped[list[Playlist]] = relationship(back_populates="parent")
    items: Mapped[list[PlaylistItem]] = relationship(
        back_populates="playlist", cascade="all, delete-orphan"
    )


class PlaylistItem(Base):
    """A track reference within a playlist, ordered by sort_index."""

    __tablename__ = "dj_playlist_items"
    __table_args__ = (
        UniqueConstraint("playlist_id", "sort_index", name="uq_playlist_items_playlist_sort"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("dj_playlists.id", ondelete="CASCADE"), index=True
    )
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    sort_index: Mapped[int] = mapped_column()
    added_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=utc_now,
    )

    playlist: Mapped[Playlist] = relationship(back_populates="items")
