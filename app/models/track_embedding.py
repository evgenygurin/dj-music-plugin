"""pgvector track embeddings."""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TrackEmbedding(Base, TimestampMixin):
    __tablename__ = "track_embeddings"
    __table_args__ = (
        UniqueConstraint("track_id", "stem_name", "embedding_type", name="uq_te_track_stem_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    stem_name: Mapped[str] = mapped_column(String(16), default="original")
    embedding_type: Mapped[str] = mapped_column(String(32))
    embedding = mapped_column(Vector(256))  # type: ignore[var-annotated]
