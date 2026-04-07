"""Domain-level helpers for Yandex Music track filtering and summarization.

Pure functions used by services (discovery, import) and tool adapters. Kept
separate from MCP presentation schemas because services must stay
framework-agnostic.
"""

from __future__ import annotations

from typing import Any

from app.config import settings


def ym_track_summary(track: object) -> dict[str, Any]:
    """Convert a YM track (client model) to a compact dict."""
    artists = (
        ", ".join(a.get("name", "?") for a in (getattr(track, "artists", None) or [])) or "Unknown"
    )
    albums = getattr(track, "albums", None) or []
    return {
        "ym_id": getattr(track, "id", ""),
        "title": getattr(track, "title", ""),
        "artists": artists,
        "duration_ms": getattr(track, "duration_ms", None),
        "album_id": str(albums[0].get("id", "")) if albums else "",
        "album_genre": albums[0].get("genre", "") if albums else "",
    }


def is_excluded_title(title: str, patterns: list[str] | None = None) -> bool:
    """Check if track title matches any exclude pattern (remix, edit, live, etc.)."""
    lower = title.lower()
    check = patterns or settings.discovery_bad_version_words.split(",")
    return any(p.strip() in lower for p in check)


def genre_ok(
    albums: list[dict[str, Any]],
    whitelist: list[str] | None = None,
    blacklist: list[str] | None = None,
) -> bool:
    """Check album genre: whitelist (accept ONLY) or blacklist (reject listed).

    Both ``None`` → use ``settings.discovery_bad_genres`` as blacklist.
    """
    if not albums:
        return True
    genre = (albums[0].get("genre") or "").lower()
    if not genre:
        return True
    if whitelist:
        return genre in [g.lower() for g in whitelist]
    bad = blacklist or settings.discovery_bad_genres.split(",")
    return genre not in [b.strip() for b in bad]
