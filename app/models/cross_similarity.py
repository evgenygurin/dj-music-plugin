"""Inter-track cross-similarity (DTW alignment)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CrossSimilarity(Base, TimestampMixin):
    __tablename__ = "cross_similarity"
    __table_args__ = (
        UniqueConstraint("track_a_id", "track_b_id", "stem_name", name="uq_cs_pair_stem"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_a_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    track_b_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    stem_name: Mapped[str] = mapped_column(String(16), default="original")
    matrix_shape: Mapped[str | None] = mapped_column(String(50), nullable=True)
    best_match_offset_ms: Mapped[float | None] = mapped_column(nullable=True)
    best_match_score: Mapped[float | None] = mapped_column(nullable=True)
    alignment_path: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )
    segment_matches: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )
