"""Audio file + beatgrid models.

Port of legacy ``app/db/models/library.py``. Drops DjCuePoint,
DjSavedLoop, DjBeatgridChangePoint per blueprint §13.2.
"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class DjLibraryItem(Base, TimestampMixin):
    __tablename__ = "dj_library_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String(1000))
    file_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    file_size: Mapped[int] = mapped_column()
    mime_type: Mapped[str] = mapped_column(String(50))
    bitrate: Mapped[int | None] = mapped_column(nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(nullable=True)
    channels: Mapped[int | None] = mapped_column(nullable=True)
    source_app: Mapped[str | None] = mapped_column(String(100), nullable=True)

    beatgrids: Mapped[list[DjBeatgrid]] = relationship(
        back_populates="library_item", cascade="all, delete-orphan"
    )


class DjBeatgrid(Base, TimestampMixin):
    __tablename__ = "dj_beatgrids"
    __table_args__ = (
        CheckConstraint("bpm BETWEEN 20 AND 300", name="ck_beatgrid_bpm_range"),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="ck_beatgrid_conf_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    library_item_id: Mapped[int] = mapped_column(
        ForeignKey("dj_library_items.id", ondelete="CASCADE"), index=True
    )
    bpm: Mapped[float] = mapped_column()
    first_downbeat_ms: Mapped[float] = mapped_column()
    grid_offset_ms: Mapped[float | None] = mapped_column(nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    variable_tempo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    canonical: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    source_app: Mapped[str | None] = mapped_column(String(100), nullable=True)

    library_item: Mapped[DjLibraryItem] = relationship(back_populates="beatgrids")
