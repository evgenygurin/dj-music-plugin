"""TransitionHistory — append-only log of real DJ transitions."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TransitionHistory(Base, TimestampMixin):
    __tablename__ = "transition_history"
    __table_args__ = (
        CheckConstraint(
            "overall_score IS NULL OR overall_score BETWEEN 0 AND 1",
            name="ck_history_score_range",
        ),
        CheckConstraint(
            "user_reaction IS NULL OR user_reaction IN ('positive', 'neutral', 'negative')",
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
    overall_score: Mapped[float | None] = mapped_column(nullable=True, index=True)
    bpm_score: Mapped[float | None] = mapped_column(nullable=True)
    energy_score: Mapped[float | None] = mapped_column(nullable=True)
    drums_score: Mapped[float | None] = mapped_column(nullable=True)
    bass_score: Mapped[float | None] = mapped_column(nullable=True)
    harmonics_score: Mapped[float | None] = mapped_column(nullable=True)
    vocals_score: Mapped[float | None] = mapped_column(nullable=True)
    style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(nullable=True)
    tempo_match_ratio: Mapped[float | None] = mapped_column(nullable=True)
    user_reaction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
