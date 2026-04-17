"""Generic track-filtering helpers.

Pure functions depending only on app.config.settings.
Used by services and controllers — intentionally kept in core.utils
so that services don't need to import from the client layer.
"""

from __future__ import annotations

from app.config import settings


def is_excluded_title(title: str, patterns: list[str] | None = None) -> bool:
    """Return True if track title matches any exclusion pattern (remix, edit, live…)."""
    lower = title.lower()
    check = patterns or settings.discovery_bad_version_words.split(",")
    return any(p.strip() in lower for p in check)
