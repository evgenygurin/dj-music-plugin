"""Pydantic response DTOs for Yandex Music MCP tools.

These models provide typed ``outputSchema`` so LLM agents know
the exact shape of every YM tool response.
"""

from __future__ import annotations

from pydantic import BaseModel

# ── ym_search ────────────────────────────────────────────


class YMSearchResponse(BaseModel):
    """Response from ``ym_search``."""

    query: str
    type: str
    tracks: list[dict[str, object]]
    albums: list[dict[str, object]]
    artists: list[dict[str, object]]
    playlists: list[dict[str, object]]


# ── ym_get_tracks ────────────────────────────────────────


class YMTrackBatch(BaseModel):
    """Response from ``ym_get_tracks``."""

    count: int
    tracks: list[dict[str, object]]


# ── ym_artist_tracks ─────────────────────────────────────


class YMArtistTrackItem(BaseModel):
    """Single track in artist-tracks response."""

    id: str
    title: str
    duration_ms: int | None = None
    albums: list[dict[str, object]] = []


class YMArtistTracksPage(BaseModel):
    """Response from ``ym_artist_tracks``."""

    artist_id: str
    offset: int
    limit: int
    sort_by: str
    count: int
    tracks: list[YMArtistTrackItem]
    has_next: bool


# ── ym_get_album ─────────────────────────────────────────


class YMAlbumResponse(BaseModel):
    """Response from ``ym_get_album``."""

    album_id: str
    album: dict[str, object]


# ── ym_playlists ─────────────────────────────────────────


class YMPlaylistActionResult(BaseModel):
    """Response from ``ym_playlists`` (all actions)."""

    action: str
    playlists: list[dict[str, object]] | None = None
    playlist: dict[str, object] | None = None
    kind: int | None = None
    new_name: str | None = None
    result: dict[str, object] | None = None
    count: int | None = None
    offset: int | None = None
    limit: int | None = None
    track_ids: list[str] | None = None
    tracks: list[dict[str, object]] | None = None
    next_offset: int | None = None
    truncated: bool | None = None
    removed: int | None = None
    not_found: list[str] | None = None
    revision: int | None = None


# ── ym_likes ─────────────────────────────────────────────


class YMLikesActionResult(BaseModel):
    """Response from ``ym_likes`` (all actions)."""

    action: str
    count: int | None = None
    offset: int | None = None
    limit: int | None = None
    liked_ids: list[str] | None = None
    next_offset: int | None = None
    truncated: bool | None = None
    track_ids: list[str] | None = None
    success: bool | None = None
