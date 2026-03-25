from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class TrackBrief(BaseModel):
    id: int
    title: str
    artist_names: list[str]
    bpm: float | None = None
    key_camelot: str | None = None
    duration_ms: int | None = None


class TrackStandard(TrackBrief):
    energy_lufs: float | None = None
    mood: str | None = None
    status: int = 0
    has_features: bool = False


class PlaylistSummary(BaseModel):
    id: int
    name: str
    track_count: int = 0
    source_of_truth: str = "local"


class SetSummary(BaseModel):
    id: int
    name: str
    track_count: int = 0
    template: str | None = None
    latest_score: float | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    total: int = 0


class YMTrackSummary(BaseModel):
    """Compact YM track info for tool output."""

    ym_id: str
    title: str
    artists: str
    duration_ms: int | None = None
    album_id: str = ""
    album_genre: str = ""


# ── Shared helpers (used by multiple tools) ──────────


def ym_track_summary(track: object) -> dict:
    """Convert a YM track (client model) to compact dict. Shared across tools."""
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
    from app.config import settings

    lower = title.lower()
    check = patterns or settings.discovery_bad_version_words.split(",")
    return any(p.strip() in lower for p in check)


def genre_ok(
    albums: list[dict],
    whitelist: list[str] | None = None,
    blacklist: list[str] | None = None,
) -> bool:
    """Check album genre: whitelist (accept ONLY) or blacklist (reject listed).

    Both None → use settings.discovery_bad_genres as blacklist.
    """
    from app.config import settings

    if not albums:
        return True
    genre = (albums[0].get("genre") or "").lower()
    if not genre:
        return True
    if whitelist:
        return genre in [g.lower() for g in whitelist]
    bad = blacklist or settings.discovery_bad_genres.split(",")
    return genre not in [b.strip() for b in bad]
