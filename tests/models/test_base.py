"""Base + TimestampMixin sanity."""

from app.models.base import Base, TimestampMixin


def test_base_is_declarative() -> None:
    assert hasattr(Base, "metadata")


def test_mixin_defines_timestamp_columns() -> None:
    assert "created_at" in TimestampMixin.__annotations__
    assert "updated_at" in TimestampMixin.__annotations__
