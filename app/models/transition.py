"""Transition — persisted scored pair. Drop TransitionCandidate per §13.2."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Transition(Base, TimestampMixin):
    __tablename__ = "transitions"
    __table_args__ = (
        CheckConstraint(
            "overall_quality IS NULL OR overall_quality BETWEEN 0 AND 1",
            name="ck_transition_quality_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    to_track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    from_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("track_sections.id", ondelete="SET NULL"), nullable=True
    )
    to_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("track_sections.id", ondelete="SET NULL"), nullable=True
    )
    overlap_ms: Mapped[int | None] = mapped_column(nullable=True)

    bpm_score: Mapped[float | None] = mapped_column(nullable=True)
    energy_score: Mapped[float | None] = mapped_column(nullable=True)
    drums_score: Mapped[float | None] = mapped_column(nullable=True)
    bass_score: Mapped[float | None] = mapped_column(nullable=True)
    harmonics_score: Mapped[float | None] = mapped_column(nullable=True)
    vocals_score: Mapped[float | None] = mapped_column(nullable=True)
    key_distance_weighted: Mapped[float | None] = mapped_column(nullable=True)
    low_conflict_score: Mapped[float | None] = mapped_column(nullable=True)
    overall_quality: Mapped[float | None] = mapped_column(nullable=True, index=True)
    hard_reject: Mapped[bool | None] = mapped_column(nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    transition_bars: Mapped[int | None] = mapped_column(nullable=True)
    fx_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    transition_recipe_json: Mapped[str | None] = mapped_column(nullable=True)
