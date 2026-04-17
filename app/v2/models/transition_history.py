"""TransitionHistory — append-only log of real DJ transitions."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.v2.models.base import Base, TimestampMixin


class TransitionHistory(Base, TimestampMixin):
    __tablename__ = "transition_history"
    __table_args__ = (
        CheckConstraint(
            "overall_score IS NULL OR overall_score BETWEEN 0 AND 1",
            name="ck_history_score_range",
        ),
        CheckConstraint(
            "reaction IS NULL OR reaction IN ('positive', 'neutral', 'negative')",
            name="ck_history_reaction_enum",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    to_track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    set_id: Mapped[int | None] = mapped_column(
        ForeignKey("dj_sets.id", ondelete="SET NULL"), nullable=True
    )
    overall_score: Mapped[float | None] = mapped_column(nullable=True, index=True)
    style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reaction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
