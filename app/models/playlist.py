"""Playlist aggregate: DjPlaylist + DjPlaylistItem.

Port of legacy ``app/db/models/playlist.py``.
"""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.shared.time import utc_now


class DjPlaylist(Base, TimestampMixin):
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

    parent: Mapped[DjPlaylist | None] = relationship(
        back_populates="children", remote_side="DjPlaylist.id"
    )
    children: Mapped[list[DjPlaylist]] = relationship(back_populates="parent")
    items: Mapped[list[DjPlaylistItem]] = relationship(
        back_populates="playlist", cascade="all, delete-orphan"
    )


class DjPlaylistItem(Base):
    __tablename__ = "dj_playlist_items"
    __table_args__ = (
        UniqueConstraint("playlist_id", "sort_index", name="uq_playlist_sort_index"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("dj_playlists.id", ondelete="CASCADE"), index=True
    )
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    sort_index: Mapped[int] = mapped_column(index=True)
    added_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    playlist: Mapped[DjPlaylist] = relationship(back_populates="items")


# Correlated subquery exposing the item count as a first-class column on
# ``DjPlaylist``. Defined after both classes are declared so the
# ``DjPlaylistItem`` reference resolves cleanly. ``column_property``
# attaches the expression to the mapped class so it participates in
# filter / sort / aggregate paths without a JOIN.
DjPlaylist.item_count = column_property(
    select(func.count(DjPlaylistItem.id))
    .where(DjPlaylistItem.playlist_id == DjPlaylist.id)
    .correlate_except(DjPlaylistItem)
    .scalar_subquery(),
)
