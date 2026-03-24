"""Tests for Base model and TimestampMixin."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class _TestTimestamp(Base, TimestampMixin):
    __tablename__ = "test_timestamps"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


async def test_timestamp_auto_populated(db):  # type: ignore[no-untyped-def]
    obj = _TestTimestamp(name="test")
    db.add(obj)
    await db.flush()
    assert obj.created_at is not None
    assert obj.updated_at is not None


async def test_timestamp_id_auto_increment(db):  # type: ignore[no-untyped-def]
    a = _TestTimestamp(name="a")
    b = _TestTimestamp(name="b")
    db.add_all([a, b])
    await db.flush()
    assert a.id is not None
    assert b.id is not None
    assert a.id != b.id
