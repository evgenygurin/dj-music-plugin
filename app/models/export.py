"""Export models (Task 16).

1 table: app_exports.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AppExport(Base, TimestampMixin):
    """Record of exporting data to a DJ application."""

    __tablename__ = "app_exports"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_app: Mapped[str] = mapped_column(String(50))
    export_format: Mapped[str] = mapped_column(String(50))
    playlist_id: Mapped[int | None] = mapped_column(
        ForeignKey("dj_playlists.id", ondelete="SET NULL"), nullable=True
    )
    file_path: Mapped[str] = mapped_column(String(1000))
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
