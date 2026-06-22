"""24 musical keys + compatibility graph (reference data).

Synced with prod Supabase schema 2026-05-07. Both reference tables are
**timestamp-free** in prod — the prior ORM applied ``TimestampMixin``
which would have added ``created_at`` / ``updated_at`` columns that do
not exist in Supabase, breaking every SELECT through the ORM. Audit
also showed ``key_edges`` carries an auto-increment ``id`` PK plus
``from_key_code`` / ``to_key_code`` (matching the ``keys`` lookup
column name); the prior ORM declared a composite PK on
``from_key`` / ``to_key`` and omitted ``id``.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Key(Base):
    __tablename__ = "keys"
    __table_args__ = (
        CheckConstraint("key_code BETWEEN 0 AND 23", name="ck_key_code_range"),
        CheckConstraint("pitch_class BETWEEN 0 AND 11", name="ck_pitch_class_range"),
        CheckConstraint("mode IN (0, 1)", name="ck_key_mode"),
    )

    key_code: Mapped[int] = mapped_column(primary_key=True)
    pitch_class: Mapped[int] = mapped_column()
    mode: Mapped[int] = mapped_column(doc="0 = minor, 1 = major")
    name: Mapped[str] = mapped_column(String(50))
    camelot: Mapped[str] = mapped_column(String(4), unique=True)


class KeyEdge(Base):
    __tablename__ = "key_edges"
    __table_args__ = (
        CheckConstraint("distance BETWEEN 0 AND 6", name="ck_key_edge_distance_range"),
        CheckConstraint("weight BETWEEN 0 AND 1", name="ck_key_edge_weight_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_key_code: Mapped[int] = mapped_column(ForeignKey("keys.key_code"), index=True)
    to_key_code: Mapped[int] = mapped_column(ForeignKey("keys.key_code"), index=True)
    distance: Mapped[int] = mapped_column()
    weight: Mapped[float] = mapped_column()
    rule_name: Mapped[str] = mapped_column(String(50))
