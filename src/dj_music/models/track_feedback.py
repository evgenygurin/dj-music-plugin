"""Per-track persistent feedback — like/ban/rating survives sessions."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from dj_music.models.base import Base, TimestampMixin


class TrackFeedback(Base, TimestampMixin):
    """Persistent per-track feedback from the DJ."""

    __tablename__ = "track_feedback"
    __table_args__ = (
        Index("idx_track_feedback_track", "track_id", unique=True),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_track_feedback_rating"),
        CheckConstraint(
            "status IN ('active', 'liked', 'banned', 'archived')",
            name="ck_track_feedback_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), unique=True)
    rating: Mapped[int] = mapped_column(default=3)  # 1-5
    status: Mapped[str] = mapped_column(
        String(20), default="active"
    )  # active/liked/banned/archived
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    play_count: Mapped[int] = mapped_column(default=0)
    skip_count: Mapped[int] = mapped_column(default=0)
