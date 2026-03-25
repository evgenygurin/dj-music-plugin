"""SQLAlchemy declarative base and shared mixins."""

from datetime import datetime

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.time import sa_now


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


class TimestampMixin:
    """Adds created_at and updated_at columns with auto-population."""

    created_at: Mapped[datetime] = mapped_column(
        default=sa_now(),
        server_default=sa_now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=sa_now(),
        server_default=sa_now(),
        onupdate=sa_now(),
    )
