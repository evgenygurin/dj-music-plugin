"""Track affinity — bidirectional pair scoring from transition history."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from dj_music.models.base import Base, TimestampMixin


class TrackAffinity(Base, TimestampMixin):
    """Aggregated pair chemistry from transition_history."""

    __tablename__ = "track_affinity"
    __table_args__ = (
        UniqueConstraint("track_a_id", "track_b_id", name="uq_track_affinity_pair"),
        Index("idx_track_affinity_a", "track_a_id"),
        Index("idx_track_affinity_b", "track_b_id"),
        Index("idx_track_affinity_sentiment", "net_sentiment"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_a_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    track_b_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    play_count: Mapped[int] = mapped_column(default=0)
    avg_score: Mapped[float | None] = mapped_column(default=None)
    like_count: Mapped[int] = mapped_column(default=0)
    ban_count: Mapped[int] = mapped_column(default=0)
    skip_count: Mapped[int] = mapped_column(default=0)
    net_sentiment: Mapped[float] = mapped_column(default=0.0)
    last_played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
