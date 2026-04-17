"""24 musical keys + compatibility graph (reference data).

``keys.key_code`` spans 0..23 per the Camelot wheel. ``key_edges``
stores weighted compatibility between any two keys (distance 0..6).
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.v2.models.base import Base, TimestampMixin


class Key(Base, TimestampMixin):
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


class KeyEdge(Base, TimestampMixin):
    __tablename__ = "key_edges"
    __table_args__ = (
        CheckConstraint("distance BETWEEN 0 AND 6", name="ck_key_edge_distance_range"),
        CheckConstraint("weight BETWEEN 0 AND 1", name="ck_key_edge_weight_range"),
    )

    from_key: Mapped[int] = mapped_column(ForeignKey("keys.key_code"), primary_key=True)
    to_key: Mapped[int] = mapped_column(ForeignKey("keys.key_code"), primary_key=True)
    distance: Mapped[int] = mapped_column()
    weight: Mapped[float] = mapped_column()
    rule_name: Mapped[str] = mapped_column(String(50))
