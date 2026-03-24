"""Musical key and key-compatibility graph models (REQUIREMENTS §2.7)."""

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Key(Base):
    """One of 24 musical keys (Camelot wheel)."""

    __tablename__ = "keys"

    key_code: Mapped[int] = mapped_column(primary_key=True)
    pitch_class: Mapped[int] = mapped_column()
    mode: Mapped[int] = mapped_column(comment="0=minor, 1=major")
    name: Mapped[str] = mapped_column(String(30))
    camelot: Mapped[str] = mapped_column(String(3), comment="e.g. 8A, 11B")

    # relationships
    edges_from: Mapped[list["KeyEdge"]] = relationship(
        foreign_keys="KeyEdge.from_key_code",
        back_populates="from_key",
        cascade="all, delete-orphan",
    )
    edges_to: Mapped[list["KeyEdge"]] = relationship(
        foreign_keys="KeyEdge.to_key_code",
        back_populates="to_key",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("key_code >= 0 AND key_code <= 23", name="ck_key_code_range"),
        CheckConstraint("pitch_class >= 0 AND pitch_class <= 11", name="ck_pitch_class_range"),
        CheckConstraint("mode IN (0, 1)", name="ck_mode_binary"),
    )

    def __repr__(self) -> str:
        return f"Key(key_code={self.key_code}, camelot={self.camelot!r}, name={self.name!r})"


class KeyEdge(Base):
    """Compatibility edge between two keys in the Camelot wheel."""

    __tablename__ = "key_edges"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_key_code: Mapped[int] = mapped_column(ForeignKey("keys.key_code"))
    to_key_code: Mapped[int] = mapped_column(ForeignKey("keys.key_code"))
    distance: Mapped[int] = mapped_column()
    weight: Mapped[float] = mapped_column()
    rule_name: Mapped[str] = mapped_column(String(50))

    # relationships
    from_key: Mapped["Key"] = relationship(
        foreign_keys=[from_key_code], back_populates="edges_from"
    )
    to_key: Mapped["Key"] = relationship(foreign_keys=[to_key_code], back_populates="edges_to")

    def __repr__(self) -> str:
        return (
            f"KeyEdge(from={self.from_key_code}, to={self.to_key_code}, "
            f"distance={self.distance}, rule={self.rule_name!r})"
        )
