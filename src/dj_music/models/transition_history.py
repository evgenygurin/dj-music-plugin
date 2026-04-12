"""Transition history — records every crossfade for learning."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from dj_music.models.base import Base, TimestampMixin


class TransitionHistory(Base, TimestampMixin):
    """One row per crossfade transition played in the panel."""

    __tablename__ = "transition_history"
    __table_args__ = (
        UniqueConstraint(
            "from_track_id",
            "to_track_id",
            "session_id",
            name="uq_transition_history_pair_session",
        ),
        CheckConstraint(
            "overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 1)",
            name="ck_transition_history_score",
        ),
        CheckConstraint(
            "user_reaction IS NULL OR user_reaction IN ('like', 'ban', 'skip', 'listened')",
            name="ck_transition_history_reaction",
        ),
        Index("idx_transition_history_from", "from_track_id"),
        Index("idx_transition_history_to", "to_track_id"),
        Index("idx_transition_history_score", "overall_score"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    to_track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    overall_score: Mapped[float | None] = mapped_column(default=None)
    bpm_score: Mapped[float | None] = mapped_column(default=None)
    harmonic_score: Mapped[float | None] = mapped_column(default=None)
    energy_score: Mapped[float | None] = mapped_column(default=None)
    spectral_score: Mapped[float | None] = mapped_column(default=None)
    groove_score: Mapped[float | None] = mapped_column(default=None)
    timbral_score: Mapped[float | None] = mapped_column(default=None)
    style: Mapped[str | None] = mapped_column(String(30), default=None)
    duration_sec: Mapped[float | None] = mapped_column(default=None)
    tempo_match_ratio: Mapped[float | None] = mapped_column(default=None)
    user_reaction: Mapped[str | None] = mapped_column(String(20), default=None)
    session_id: Mapped[str | None] = mapped_column(String(64), default=None)
