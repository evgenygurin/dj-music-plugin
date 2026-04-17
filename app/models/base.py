"""SQLAlchemy declarative Base + TimestampMixin for v2 models.

All aggregates inherit from ``Base``; rows that need ``created_at`` /
``updated_at`` columns additionally mix in ``TimestampMixin``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.shared.time import sa_now


class Base(DeclarativeBase):
    """Declarative base for every v2 ORM model."""


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns with DB-side defaults."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=sa_now(),
        server_default=sa_now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=sa_now(),
        server_default=sa_now(),
        onupdate=sa_now(),
    )
