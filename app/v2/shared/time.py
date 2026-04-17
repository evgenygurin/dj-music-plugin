"""Centralized time utilities (v2).

Single source of truth for all datetime operations. All timestamps are UTC.
Use these instead of direct datetime calls.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func


def utc_now() -> datetime:
    """Current UTC datetime. Use for Python-side timestamps."""
    return datetime.now(UTC)


def utc_timestamp_iso() -> str:
    """Current UTC datetime as ISO-8601 string. Use for JSON metadata."""
    return utc_now().isoformat()


def sa_now():  # type: ignore[no-untyped-def]
    """SQLAlchemy NOW() expression for column defaults.

    Use as ``mapped_column(default=sa_now(), server_default=sa_now())`` —
    generates ``NOW()`` on the database side.
    """
    return func.now()
