"""Shared Pydantic DTOs used across the services and MCP tools layers.

Single source of truth for framework-agnostic structured output models.
Services return these types directly; MCP tools expose them via
``structuredContent`` without additional mapping.

Layer organisation:
- :mod:`common` — pagination envelope
- :mod:`track` — TrackBrief, TrackStandard
- :mod:`playlist` — PlaylistSummary
- :mod:`set` — SetSummary
- :mod:`yandex` — YMTrackSummary

Domain helpers (``ym_track_summary``, ``is_excluded_title``, ``genre_ok``)
live in :mod:`app.clients.ym.filters` — they are filtering utilities, not
schemas, and were moved out of this module to keep concerns separated.
"""

from __future__ import annotations

from app.schemas.common import PaginatedResponse
from app.schemas.playlist import PlaylistSummary
from app.schemas.set import SetSummary
from app.schemas.track import TrackBrief, TrackStandard
from app.schemas.yandex import YMTrackSummary
from app.schemas.ym_responses import (
    YMAlbumResponse,
    YMArtistTracksPage,
    YMLikesActionResult,
    YMPlaylistActionResult,
    YMSearchResponse,
    YMTrackBatch,
)

__all__ = [
    "PaginatedResponse",
    "PlaylistSummary",
    "SetSummary",
    "TrackBrief",
    "TrackStandard",
    "YMAlbumResponse",
    "YMArtistTracksPage",
    "YMLikesActionResult",
    "YMPlaylistActionResult",
    "YMSearchResponse",
    "YMTrackBatch",
    "YMTrackSummary",
]
