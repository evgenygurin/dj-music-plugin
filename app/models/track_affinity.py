"""TrackAffinity — aggregated A-B pair stats, computed from history."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TrackAffinity(Base, TimestampMixin):
    __tablename__ = "track_affinity"
    __table_args__ = (
        UniqueConstraint("track_a_id", "track_b_id", name="uq_affinity_pair"),
        CheckConstraint(
            "avg_score IS NULL OR avg_score BETWEEN 0 AND 1",
            name="ck_affinity_score_range",
        ),
        CheckConstraint("play_count >= 0", name="ck_affinity_play_count_nonneg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_a_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    track_b_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    play_count: Mapped[int] = mapped_column(default=0, server_default="0")
    positive_count: Mapped[int] = mapped_column(default=0, server_default="0")
    negative_count: Mapped[int] = mapped_column(default=0, server_default="0")
    avg_score: Mapped[float | None] = mapped_column(nullable=True)
