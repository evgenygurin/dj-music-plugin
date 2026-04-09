"""Transition models (Task 14).

2 tables: transitions, transition_candidates.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


def _score_check(col: str) -> CheckConstraint:
    """Helper for 0-1 range check on nullable float columns."""
    return CheckConstraint(
        f"{col} IS NULL OR ({col} >= 0 AND {col} <= 1)",
        name=f"ck_transitions_{col}",
    )


class Transition(Base, TimestampMixin):
    """Scored quality of playing two tracks in sequence."""

    __tablename__ = "transitions"
    __table_args__ = (
        UniqueConstraint("from_track_id", "to_track_id", name="uq_transitions_from_to"),
        _score_check("bpm_score"),
        _score_check("energy_score"),
        _score_check("harmonic_score"),
        _score_check("spectral_score"),
        _score_check("groove_score"),
        _score_check("timbral_score"),
        _score_check("key_distance_weighted"),
        _score_check("low_conflict_score"),
        _score_check("overall_quality"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    to_track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    from_section_id: Mapped[int | None] = mapped_column(nullable=True)
    to_section_id: Mapped[int | None] = mapped_column(nullable=True)
    overlap_ms: Mapped[int | None] = mapped_column(nullable=True)

    # Score fields (all 0-1, nullable)
    bpm_score: Mapped[float | None] = mapped_column(nullable=True)
    energy_score: Mapped[float | None] = mapped_column(nullable=True)
    harmonic_score: Mapped[float | None] = mapped_column(nullable=True)
    spectral_score: Mapped[float | None] = mapped_column(nullable=True)
    groove_score: Mapped[float | None] = mapped_column(nullable=True)
    #: 6th TransitionScorer component: deeper timbral texture similarity
    #: (spectral complexity + pitch salience + band correlation).
    timbral_score: Mapped[float | None] = mapped_column(nullable=True)
    #: ``True`` when a hard constraint (BPM gap, key distance, LUFS gap)
    #: forced ``overall_quality`` to 0 — preserved across cache hits so
    #: clients can distinguish "bad score" from "explicit reject".
    hard_reject: Mapped[bool | None] = mapped_column(nullable=True, default=None)
    #: Human-readable reason for a hard reject (e.g. ``"bpm_diff=12"``).
    reject_reason: Mapped[str | None] = mapped_column(nullable=True, default=None)
    key_distance_weighted: Mapped[float | None] = mapped_column(nullable=True)
    low_conflict_score: Mapped[float | None] = mapped_column(nullable=True)
    overall_quality: Mapped[float | None] = mapped_column(nullable=True)


class TransitionCandidate(Base, TimestampMixin):
    """A potential transition before full scoring."""

    __tablename__ = "transition_candidates"
    __table_args__ = (
        UniqueConstraint("from_track_id", "to_track_id", name="uq_transition_candidates_from_to"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    to_track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    bpm_distance: Mapped[float | None] = mapped_column(nullable=True)
    key_distance: Mapped[int | None] = mapped_column(nullable=True)
    embedding_similarity: Mapped[float | None] = mapped_column(nullable=True)
    energy_delta: Mapped[float | None] = mapped_column(nullable=True)
    fully_scored: Mapped[bool] = mapped_column(default=False, server_default="false")
