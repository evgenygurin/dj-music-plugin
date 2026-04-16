"""Platform-agnostic Pydantic response DTOs for MCP tools.

These models provide typed ``outputSchema`` so LLM agents know
the exact shape of every platform tool response.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

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

    requested: int | None = None
    count: int
    unresolved_track_ids: list[str] = Field(default_factory=list)
    error: str | None = None
    tracks: list[dict[str, object]]


class PlatformTrackIdMapItem(BaseModel):
    """Single local->platform ID mapping row."""

    local_track_id: int
    platform_track_id: str | None = None
    found: bool


class PlatformTrackIdMapResult(BaseModel):
    """Response from ``resolve_platform_track_ids``."""

    platform: str
    requested: int
    resolved: int
    unresolved_track_ids: list[int]
    strict_violation: bool = False
    error: str | None = None
    mappings: list[PlatformTrackIdMapItem]


# ── get_platform_artist_tracks ───────────────────────────────


class ArtistTrackItem(BaseModel):
    """Single track in artist-tracks response."""

    id: str
    title: str
    duration_ms: int | None = None
    albums: list[dict[str, object]] = Field(default_factory=list)


class ArtistTracksPage(BaseModel):
    """Response from ``get_platform_artist_tracks``."""

    artist_id: str
    offset: int
    limit: int
    sort_by: str
    count: int
    tracks: list[ArtistTrackItem]
    has_next: bool


# ── get_platform_album ───────────────────────────────────────


class AlbumResult(BaseModel):
    """Response from ``get_platform_album``."""

    album_id: str
    album: dict[str, object]


# ── platform_playlists ───────────────────────────────────────


class PlaylistListResult(BaseModel):
    """Response for ``platform_playlists(action='list')``."""

    action: Literal["list"]
    playlists: list[dict[str, object]]
    count: int
    offset: int
    limit: int
    next_offset: int | None = None
    truncated: bool


class PlaylistGetResult(BaseModel):
    """Response for ``platform_playlists(action='get')``."""

    action: Literal["get"]
    playlist_id: str
    playlist: dict[str, object]


class PlaylistGetTracksResult(BaseModel):
    """Response for ``platform_playlists(action='get_tracks')``."""

    action: Literal["get_tracks"]
    playlist_id: str
    count: int
    offset: int
    limit: int
    track_ids: list[str]
    tracks: list[dict[str, object]]
    next_offset: int | None = None
    truncated: bool


class PlaylistCreateResult(BaseModel):
    """Response for ``platform_playlists(action='create')``."""

    action: Literal["create"]
    playlist: dict[str, object]


class PlaylistRenameResult(BaseModel):
    """Response for ``platform_playlists(action='rename')``."""

    action: Literal["rename"]
    playlist_id: str
    new_name: str


class PlaylistDeleteResult(BaseModel):
    """Response for ``platform_playlists(action='delete')``."""

    action: Literal["delete"]
    playlist_id: str


class PlaylistAddTracksResult(BaseModel):
    """Response for ``platform_playlists(action='add_tracks')``."""

    action: Literal["add_tracks"]
    playlist_id: str
    result: dict[str, object] | bool


class PlaylistRemoveTracksResult(BaseModel):
    """Response for ``platform_playlists(action='remove_tracks')``."""

    action: Literal["remove_tracks"]
    playlist_id: str
    removed: int
    result: dict[str, object]


class PlaylistUpdateResult(BaseModel):
    """Response for ``platform_playlists(action='update')``."""

    action: Literal["update"]
    playlist_id: str
    removed: int
    added: int
    result: dict[str, object] | bool


PlaylistActionResult = Annotated[
    PlaylistListResult
    | PlaylistGetResult
    | PlaylistGetTracksResult
    | PlaylistCreateResult
    | PlaylistRenameResult
    | PlaylistDeleteResult
    | PlaylistAddTracksResult
    | PlaylistRemoveTracksResult
    | PlaylistUpdateResult,
    Field(discriminator="action"),
]


# ── platform_liked_tracks ────────────────────────────────────


class LikesGetLikedResult(BaseModel):
    """Response for ``platform_liked_tracks(action='get_liked')``."""

    action: Literal["get_liked"]
    count: int
    offset: int
    limit: int
    liked_ids: list[str]
    next_offset: int | None = None
    truncated: bool


class LikesAddResult(BaseModel):
    """Response for ``platform_liked_tracks(action='add')``."""

    action: Literal["add"]
    track_ids: list[str]
    success: bool


class LikesRemoveResult(BaseModel):
    """Response for ``platform_liked_tracks(action='remove')``."""

    action: Literal["remove"]
    track_ids: list[str]
    success: bool


LikesActionResult = Annotated[
    LikesGetLikedResult | LikesAddResult | LikesRemoveResult,
    Field(discriminator="action"),
]
