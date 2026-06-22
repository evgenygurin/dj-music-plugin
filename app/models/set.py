"""DJ Set aggregate: DjSet + DjSetVersion + DjSetItem.

Port of legacy ``app/db/models/set.py``. Drops SetConstraint + SetFeedback
per blueprint §13.2 (0 rows, feature unimplemented).
"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class DjSet(Base, TimestampMixin):
    __tablename__ = "dj_sets"
    __table_args__ = (
        CheckConstraint(
            "target_bpm_min IS NULL OR target_bpm_min BETWEEN 20 AND 300",
            name="ck_set_bpm_min_range",
        ),
        CheckConstraint(
            "target_bpm_max IS NULL OR target_bpm_max BETWEEN 20 AND 300",
            name="ck_set_bpm_max_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    target_bpm_min: Mapped[int | None] = mapped_column(nullable=True)
    target_bpm_max: Mapped[int | None] = mapped_column(nullable=True)
    target_energy_arc: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_playlist_id: Mapped[int | None] = mapped_column(
        ForeignKey("dj_playlists.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Prod has this column for sets that were originally pushed to YM.
    # Prior ORM omitted it; reads worked but writes never preserved the
    # link. Currently 0 rows populate it, but the column is live.
    ym_playlist_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    versions: Mapped[list[DjSetVersion]] = relationship(
        back_populates="dj_set", cascade="all, delete-orphan"
    )


class DjSetVersion(Base, TimestampMixin):
    __tablename__ = "dj_set_versions"
    __table_args__ = (
        CheckConstraint(
            "quality_score IS NULL OR quality_score BETWEEN 0 AND 1",
            name="ck_version_quality_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    set_id: Mapped[int] = mapped_column(ForeignKey("dj_sets.id", ondelete="CASCADE"), index=True)
    # Prod: label is nullable.
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generator_run_meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(nullable=True)

    dj_set: Mapped[DjSet] = relationship(back_populates="versions")
    items: Mapped[list[DjSetItem]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )


class DjSetItem(Base, TimestampMixin):
    __tablename__ = "dj_set_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("dj_set_versions.id", ondelete="CASCADE"), index=True
    )
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    sort_index: Mapped[int] = mapped_column(index=True)
    transition_id: Mapped[int | None] = mapped_column(
        ForeignKey("transitions.id", ondelete="SET NULL"), nullable=True
    )
    out_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("track_sections.id", ondelete="SET NULL"), nullable=True
    )
    in_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("track_sections.id", ondelete="SET NULL"), nullable=True
    )
    mix_in_point_ms: Mapped[int | None] = mapped_column(nullable=True)
    mix_out_point_ms: Mapped[int | None] = mapped_column(nullable=True)
    planned_eq: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    version: Mapped[DjSetVersion] = relationship(back_populates="items")
