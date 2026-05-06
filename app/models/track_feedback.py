"""Per-track feedback (one row per track) — synced with prod schema 2026-05-07.

Replaces the prior ``kind / rating / notes`` triplet with the actual prod
shape (~3 rows live in Supabase): a single row per track keyed by
``track_id`` (UNIQUE), tracking rating + lifecycle status + play / skip
counters. The previous ORM expected a ``kind`` column that was never
applied to the production DB; the prod schema instead carries
``status`` (active / liked / banned / archived) + ``play_count`` /
``skip_count``. ``track_feedback`` now mirrors prod exactly so
``entity_*(track_feedback, …)`` works against Supabase rows.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TrackFeedback(Base, TimestampMixin):
    __tablename__ = "track_feedback"
    __table_args__ = (
        UniqueConstraint("track_id", name="track_feedback_track_id_key"),
        CheckConstraint(
            "status IN ('active', 'liked', 'banned', 'archived')",
            name="ck_track_feedback_status",
        ),
        CheckConstraint(
            "rating BETWEEN 1 AND 5",
            name="ck_track_feedback_rating",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    # Per CHECK constraint above; default 3 (neutral) so a row can be
    # created with status alone (e.g. status='liked' without explicit rating).
    rating: Mapped[int] = mapped_column(default=3, server_default="3")
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    play_count: Mapped[int] = mapped_column(default=0, server_default="0")
    skip_count: Mapped[int] = mapped_column(default=0, server_default="0")
