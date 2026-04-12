"""DJ Set models (Task 13).

5 tables: dj_sets, dj_set_versions, dj_set_items, dj_set_constraints, dj_set_feedback.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dj_music.models.base import Base, TimestampMixin


class DjSet(Base, TimestampMixin):
    """A planned DJ performance."""

    __tablename__ = "dj_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    target_bpm_min: Mapped[float | None] = mapped_column(nullable=True)
    target_bpm_max: Mapped[float | None] = mapped_column(nullable=True)
    target_energy_arc: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_playlist_id: Mapped[int | None] = mapped_column(
        ForeignKey("dj_playlists.id", ondelete="SET NULL"), nullable=True, index=True
    )
    ym_playlist_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    versions: Mapped[list[SetVersion]] = relationship(
        back_populates="dj_set", cascade="all, delete-orphan"
    )
    constraints: Mapped[list[SetConstraint]] = relationship(
        back_populates="dj_set", cascade="all, delete-orphan"
    )


class SetVersion(Base, TimestampMixin):
    """A snapshot of a set's track ordering."""

    __tablename__ = "dj_set_versions"
    __table_args__ = (
        CheckConstraint(
            "quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 1)",
            name="ck_set_versions_quality_score",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    set_id: Mapped[int] = mapped_column(ForeignKey("dj_sets.id", ondelete="CASCADE"), index=True)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    generator_run_meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(nullable=True)

    dj_set: Mapped[DjSet] = relationship(back_populates="versions")
    items: Mapped[list[SetItem]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )
    feedback: Mapped[list[SetFeedback]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )


class SetItem(Base, TimestampMixin):
    """A track in a set version."""

    __tablename__ = "dj_set_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("dj_set_versions.id", ondelete="CASCADE"), index=True
    )
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    sort_index: Mapped[int] = mapped_column()
    transition_id: Mapped[int | None] = mapped_column(
        ForeignKey("transitions.id", ondelete="SET NULL"), nullable=True
    )
    in_section_id: Mapped[int | None] = mapped_column(nullable=True)
    out_section_id: Mapped[int | None] = mapped_column(nullable=True)
    mix_in_point_ms: Mapped[int | None] = mapped_column(nullable=True)
    mix_out_point_ms: Mapped[int | None] = mapped_column(nullable=True)
    planned_eq: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    pinned: Mapped[bool] = mapped_column(default=False, server_default="false")

    version: Mapped[SetVersion] = relationship(back_populates="items")


class SetConstraint(Base, TimestampMixin):
    """A rule for set generation."""

    __tablename__ = "dj_set_constraints"

    id: Mapped[int] = mapped_column(primary_key=True)
    set_id: Mapped[int] = mapped_column(ForeignKey("dj_sets.id", ondelete="CASCADE"), index=True)
    constraint_type: Mapped[str] = mapped_column(String(200))
    constraint_value: Mapped[str] = mapped_column(Text)

    dj_set: Mapped[DjSet] = relationship(back_populates="constraints")


class SetFeedback(Base, TimestampMixin):
    """User/crowd rating of a set version or item."""

    __tablename__ = "dj_set_feedback"
    __table_args__ = (
        CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name="ck_set_feedback_rating",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("dj_set_versions.id", ondelete="CASCADE"), index=True
    )
    set_item_id: Mapped[int | None] = mapped_column(nullable=True)
    rating: Mapped[int] = mapped_column()
    feedback_type: Mapped[str] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    version: Mapped[SetVersion] = relationship(back_populates="feedback")
