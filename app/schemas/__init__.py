"""Shared Pydantic DTOs used across the services and MCP tools layers.

Single source of truth for framework-agnostic structured output models.

Layer organisation:
- :mod:`common` — pagination envelope
- :mod:`track` — TrackBrief, TrackStandard
- :mod:`playlist` — PlaylistSummary
- :mod:`set` — SetSummary
- :mod:`yandex` — YMTrackSummary
- :mod:`platform_responses` — platform-agnostic tool response DTOs

Domain helpers (``is_excluded_title``, ``genre_ok``)
live in :mod:`app.clients.ym.filters` (moved to :mod:`app.core.utils.filters` in Phase 1, Task 3).
"""

from __future__ import annotations

from app.schemas.common import PaginatedResponse
from app.schemas.platform_responses import (
    AlbumResult,
    ArtistTrackItem,
    ArtistTracksPage,
    LikesActionResult,
    PlatformSearchResult,
    PlatformTrackBatch,
    PlaylistActionResult,
)
from app.schemas.playlist import PlaylistSummary
from app.schemas.set import SetSummary
from app.schemas.track import TrackBrief, TrackStandard
from app.schemas.yandex import YMTrackSummary

# Legacy aliases — remove after Phase 3
YMAlbumResponse = AlbumResult
YMArtistTrackItem = ArtistTrackItem
YMArtistTracksPage = ArtistTracksPage
YMLikesActionResult = LikesActionResult
YMPlaylistActionResult = PlaylistActionResult
YMSearchResponse = PlatformSearchResult
YMTrackBatch = PlatformTrackBatch

__all__ = [
    "AlbumResult",
    "ArtistTrackItem",
    "ArtistTracksPage",
    "LikesActionResult",
    "PaginatedResponse",
    "PlatformSearchResult",
    "PlatformTrackBatch",
    "PlaylistActionResult",
    "PlaylistSummary",
    "SetSummary",
    "TrackBrief",
    "TrackStandard",
    # Legacy aliases
    "YMAlbumResponse",
    "YMArtistTrackItem",
    "YMArtistTracksPage",
    "YMLikesActionResult",
    "YMPlaylistActionResult",
    "YMSearchResponse",
    "YMTrackBatch",
    "YMTrackSummary",
]
