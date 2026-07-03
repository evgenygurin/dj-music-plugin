"""TrackAffinity — aggregated A→B pair stats, synced with prod schema 2026-05-07.

Prior ORM expected ``positive_count`` / ``negative_count`` columns that
were never applied to Supabase; the production table instead carries
``like_count`` / ``ban_count`` / ``skip_count`` / ``net_sentiment`` (a
denormalised score) plus ``last_played_at``. ``track_affinity`` now
mirrors prod 1:1.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TrackAffinity(Base, TimestampMixin):
    __tablename__ = "track_affinity"
    __table_args__ = (
        UniqueConstraint("track_a_id", "track_b_id", name="uq_track_affinity_pair"),
        CheckConstraint(
            "avg_score IS NULL OR avg_score BETWEEN 0 AND 1",
            name="ck_affinity_score_range",
        ),
        CheckConstraint("play_count >= 0", name="ck_affinity_play_count_nonneg"),
        # A track's affinity with itself is degenerate — there is no
        # "pair history" to record. Mirrors the pydantic gate on
        # TrackAffinityCreate (audit iter 54); this is the DB-level
        # backstop so a self-pair cannot exist even via a raw insert.
        CheckConstraint("track_a_id <> track_b_id", name="ck_affinity_distinct_pair"),
        Index("idx_track_affinity_a", "track_a_id"),
        Index("idx_track_affinity_b", "track_b_id"),
        Index("idx_track_affinity_sentiment", "net_sentiment"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_a_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    track_b_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    play_count: Mapped[int] = mapped_column(default=0, server_default="0")
    avg_score: Mapped[float | None] = mapped_column(nullable=True)
    like_count: Mapped[int] = mapped_column(default=0, server_default="0")
    ban_count: Mapped[int] = mapped_column(default=0, server_default="0")
    skip_count: Mapped[int] = mapped_column(default=0, server_default="0")
    # Denormalised affinity score in [-1, 1]; updated by feedback handler.
    net_sentiment: Mapped[float] = mapped_column(default=0.0, server_default="0")
    last_played_at: Mapped[datetime | None] = mapped_column(nullable=True)
