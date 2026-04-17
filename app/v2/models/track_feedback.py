"""Per-track feedback: like / ban / rate."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.v2.models.base import Base, TimestampMixin


class TrackFeedback(Base, TimestampMixin):
    __tablename__ = "track_feedback"
    __table_args__ = (
        CheckConstraint("kind IN ('like', 'ban', 'rate')", name="ck_feedback_kind"),
        CheckConstraint(
            "rating IS NULL OR rating BETWEEN 1 AND 5",
            name="ck_feedback_rating_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))
    rating: Mapped[int | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
