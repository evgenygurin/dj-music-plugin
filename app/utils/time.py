"""Centralized time utilities.

Single source of truth for all datetime operations in the project.
All timestamps are UTC. Use these functions instead of direct datetime calls.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func

# ── Python-side (for application code) ────────────────


def utc_now() -> datetime:
    """Current UTC datetime. Use for Python-side timestamps."""
    return datetime.now(UTC)


def utc_timestamp_iso() -> str:
    """Current UTC datetime as ISO 8601 string. Use for JSON metadata."""
    return utc_now().isoformat()


# ── SQLAlchemy-side (for model defaults) ──────────────

# Use these as mapped_column(default=..., server_default=...)
# They generate SQL NOW() on the database side.

sa_now = func.now
"""SQLAlchemy func.now — call as sa_now() in mapped_column defaults."""
