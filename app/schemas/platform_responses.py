"""Platform-agnostic Pydantic response DTOs for MCP tools.

These models provide typed ``outputSchema`` so LLM agents know
the exact shape of every platform tool response.
"""

from __future__ import annotations

from pydantic import BaseModel

# ── search ──────────────────────────────────────────────────


class PlatformSearchResult(BaseModel):
    """Response from ``search_platform``."""

    query: str
    type: str
    tracks: list[dict[str, object]]
    albums: list[dict[str, object]]
    artists: list[dict[str, object]]
    playlists: list[dict[str, object]]


# ── get_platform_tracks ──────────────────────────────────────


class PlatformTrackBatch(BaseModel):
    """Response from ``get_platform_tracks``."""

    count: int
    tracks: list[dict[str, object]]


# ── get_artist_tracks ────────────────────────────────────────


class ArtistTrackItem(BaseModel):
    """Single track in artist-tracks response."""

    id: str
    title: str
    duration_ms: int | None = None
    albums: list[dict[str, object]] = []


class ArtistTracksPage(BaseModel):
    """Response from ``get_artist_tracks``."""

    artist_id: str
    offset: int
    limit: int
    sort_by: str
    count: int
    tracks: list[ArtistTrackItem]
    has_next: bool


# ── get_album ────────────────────────────────────────────────


class AlbumResult(BaseModel):
    """Response from ``get_album``."""

    album_id: str
    album: dict[str, object]


# ── platform_playlists ───────────────────────────────────────


class PlaylistActionResult(BaseModel):
    """Response from ``platform_playlists`` (all actions)."""

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


# ── platform_likes ───────────────────────────────────────────


class LikesActionResult(BaseModel):
    """Response from ``platform_likes`` (all actions)."""

    action: str
    count: int | None = None
    offset: int | None = None
    limit: int | None = None
    liked_ids: list[str] | None = None
    next_offset: int | None = None
    truncated: bool | None = None
    track_ids: list[str] | None = None
    success: bool | None = None
