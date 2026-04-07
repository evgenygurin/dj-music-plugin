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
live in :mod:`app.core.ym_filters` — they are filtering utilities, not
schemas, and were moved out of this module to keep concerns separated.
"""

from __future__ import annotations

from app.core.schemas.common import PaginatedResponse
from app.core.schemas.playlist import PlaylistSummary
from app.core.schemas.set import SetSummary
from app.core.schemas.track import TrackBrief, TrackStandard
from app.core.schemas.yandex import YMTrackSummary

__all__ = [
    "PaginatedResponse",
    "PlaylistSummary",
    "SetSummary",
    "TrackBrief",
    "TrackStandard",
    "YMTrackSummary",
]
