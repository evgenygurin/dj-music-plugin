"""Taxonomy constants for MCP tools.

Eliminates the magic strings that were scattered across every ``@tool``
decorator — tags, read-only annotations, timeouts, icons, meta. One
canonical source, type-safe enums, no literals in tool modules.

Usage::

    from app.controllers.tools._shared import (
        ANNOTATIONS_READ_ONLY,
        ICON_TRACKS,
        TOOL_META,
        ToolCategory,
        ToolTimeout,
    )

    @tool(
        title="List Tracks",
        tags={ToolCategory.CORE.value},
        annotations=ANNOTATIONS_READ_ONLY,
        icons=ICON_TRACKS,
        meta=TOOL_META,
    )
    async def list_tracks(...) -> PaginatedResponse[TrackBrief]: ...
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Final

from mcp.types import Icon


class ToolCategory(StrEnum):
    """Stable tag set for MCP tool visibility and grouping.

    The values are the tag strings consumed by FastMCP's
    ``mcp.enable(tags=...)`` / ``mcp.disable(tags=...)`` filtering.
    """

    CORE = "core"
    SETS = "sets"
    DELIVERY = "delivery"
    DISCOVERY = "discovery"
    CURATION = "curation"
    SYNC = "sync"
    YM = "ym"
    AUDIO = "audio"
    ATOMIC = "atomic"
    ADMIN = "admin"


# ── Annotation presets ────────────────────────────────────────────
#
# FastMCP's ``@tool`` expects ``dict[str, Any]`` for annotations.
# MCP spec hints: readOnlyHint, idempotentHint, destructiveHint,
# openWorldHint. We define semantic presets covering all our use-cases.

ANNOTATIONS_READ_ONLY: Final[dict[str, Any]] = {
    "readOnlyHint": True,
    "idempotentHint": True,
}

ANNOTATIONS_READ_ONLY_OPEN_WORLD: Final[dict[str, Any]] = {
    "readOnlyHint": True,
    "idempotentHint": True,
    "openWorldHint": True,
}

ANNOTATIONS_WRITE: Final[dict[str, Any]] = {
    "readOnlyHint": False,
}

ANNOTATIONS_WRITE_IDEMPOTENT: Final[dict[str, Any]] = {
    "readOnlyHint": False,
    "idempotentHint": True,
}

ANNOTATIONS_WRITE_DESTRUCTIVE: Final[dict[str, Any]] = {
    "readOnlyHint": False,
    "destructiveHint": True,
}

ANNOTATIONS_WRITE_OPEN_WORLD: Final[dict[str, Any]] = {
    "readOnlyHint": False,
    "openWorldHint": True,
}

ANNOTATIONS_WRITE_DESTRUCTIVE_OPEN: Final[dict[str, Any]] = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "openWorldHint": True,
}


class ToolTimeout:
    """Canonical tool execution timeouts (seconds).

    Categories map to operation weight, not to specific tools. Adjust in
    one place rather than searching the codebase for literal ``600.0``.
    """

    #: Interactive operations (score_pair, filter, search) — up to 5 minutes.
    MEDIUM: Final[float] = 300.0

    #: Pipeline operations (build_set, analyze_track) — up to 15 minutes.
    HEAVY: Final[float] = 900.0

    #: Long-running batch jobs (analyze_batch, deliver_set) — up to 30 minutes.
    BATCH: Final[float] = 1800.0


# ── Meta ──────────────────────────────────────────────────────────

from app._version import __version__ as _v

TOOL_META: Final[dict[str, Any]] = {
    "version": _v,
    "author": "dj-music-plugin",
}

RESOURCE_META: Final[dict[str, Any]] = {
    "version": _v,
}


# ── Icons (data-URI SVG, no external hosting needed) ─────────────
#
# Each list contains one Icon with an inline SVG data-URI.
# Categories: tracks, playlists, sets, search, audio, delivery,
# discovery, curation, sync, ym, admin, decks, mixer, memory.


def _svg_icon(svg_body: str) -> list[Icon]:
    """Build an Icon list from a minimal SVG body (24x24 viewBox)."""
    uri = (
        "data:image/svg+xml,"
        "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' "
        "fill='none' stroke='currentColor' stroke-width='2' "
        "stroke-linecap='round' stroke-linejoin='round'%3E"
        f"{svg_body}%3C/svg%3E"
    )
    return [Icon(src=uri)]


# Music note — tracks, features
ICON_TRACKS: Final[list[Icon]] = _svg_icon(
    "%3Cpath d='M9 18V5l12-2v13'/%3E"
    "%3Ccircle cx='6' cy='18' r='3'/%3E"
    "%3Ccircle cx='18' cy='16' r='3'/%3E"
)

# List — playlists
ICON_PLAYLISTS: Final[list[Icon]] = _svg_icon(
    "%3Cline x1='8' y1='6' x2='21' y2='6'/%3E"
    "%3Cline x1='8' y1='12' x2='21' y2='12'/%3E"
    "%3Cline x1='8' y1='18' x2='21' y2='18'/%3E"
    "%3Cline x1='3' y1='6' x2='3.01' y2='6'/%3E"
    "%3Cline x1='3' y1='12' x2='3.01' y2='12'/%3E"
    "%3Cline x1='3' y1='18' x2='3.01' y2='18'/%3E"
)

# Disc — sets
ICON_SETS: Final[list[Icon]] = _svg_icon(
    "%3Ccircle cx='12' cy='12' r='10'/%3E%3Ccircle cx='12' cy='12' r='3'/%3E"
)

# Search
ICON_SEARCH: Final[list[Icon]] = _svg_icon(
    "%3Ccircle cx='11' cy='11' r='8'/%3E%3Cline x1='21' y1='21' x2='16.65' y2='16.65'/%3E"
)

# Waveform — audio analysis
ICON_AUDIO: Final[list[Icon]] = _svg_icon("%3Cpath d='M2 12h2l3-9 4 18 4-18 3 9h2'/%3E")

# Package — delivery/export
ICON_DELIVERY: Final[list[Icon]] = _svg_icon(
    "%3Cpath d='M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8"
    "a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z'/%3E"
    "%3Cpolyline points='3.27 6.96 12 12.01 20.73 6.96'/%3E"
    "%3Cline x1='12' y1='22.08' x2='12' y2='12'/%3E"
)

# Compass — discovery
ICON_DISCOVERY: Final[list[Icon]] = _svg_icon(
    "%3Ccircle cx='12' cy='12' r='10'/%3E"
    "%3Cpolygon points='16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76'/%3E"
)

# Layers — curation
ICON_CURATION: Final[list[Icon]] = _svg_icon(
    "%3Cpolygon points='12 2 2 7 12 12 22 7 12 2'/%3E"
    "%3Cpolyline points='2 17 12 22 22 17'/%3E"
    "%3Cpolyline points='2 12 12 17 22 12'/%3E"
)

# Refresh — sync
ICON_SYNC: Final[list[Icon]] = _svg_icon(
    "%3Cpolyline points='23 4 23 10 17 10'/%3E"
    "%3Cpolyline points='1 20 1 14 7 14'/%3E"
    "%3Cpath d='M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15'/%3E"
)

# Globe — Yandex Music
ICON_YM: Final[list[Icon]] = _svg_icon(
    "%3Ccircle cx='12' cy='12' r='10'/%3E"
    "%3Cline x1='2' y1='12' x2='22' y2='12'/%3E"
    "%3Cpath d='M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10"
    " 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z'/%3E"
)

# Settings — admin
ICON_ADMIN: Final[list[Icon]] = _svg_icon(
    "%3Ccircle cx='12' cy='12' r='3'/%3E"
    "%3Cpath d='M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83"
    " 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33"
    " 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09"
    "A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06"
    "a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06"
    "A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09"
    "A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06"
    "a2 2 0 010-2.83 2 2 0 012.83 0l.06.06"
    "a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09"
    "a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06"
    "a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06"
    "a1.65 1.65 0 00-.33 1.82V9c.26.604.852.997 1.51 1H21a2 2 0 010 4h-.09"
    "a1.65 1.65 0 00-1.51 1z'/%3E"
)

# Play — decks
ICON_DECKS: Final[list[Icon]] = _svg_icon("%3Cpolygon points='5 3 19 12 5 21 5 3'/%3E")

# Sliders — mixer
ICON_MIXER: Final[list[Icon]] = _svg_icon(
    "%3Cline x1='4' y1='21' x2='4' y2='14'/%3E"
    "%3Cline x1='4' y1='10' x2='4' y2='3'/%3E"
    "%3Cline x1='12' y1='21' x2='12' y2='12'/%3E"
    "%3Cline x1='12' y1='8' x2='12' y2='3'/%3E"
    "%3Cline x1='20' y1='21' x2='20' y2='16'/%3E"
    "%3Cline x1='20' y1='12' x2='20' y2='3'/%3E"
    "%3Cline x1='1' y1='14' x2='7' y2='14'/%3E"
    "%3Cline x1='9' y1='8' x2='15' y2='8'/%3E"
    "%3Cline x1='17' y1='16' x2='23' y2='16'/%3E"
)

# Brain — memory/affinity/feedback/scoring/history
ICON_MEMORY: Final[list[Icon]] = _svg_icon(
    "%3Cpath d='M12 2a7 7 0 017 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 01-2 2h-4"
    "a2 2 0 01-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 017-7z'/%3E"
    "%3Cline x1='9' y1='21' x2='15' y2='21'/%3E"
)

# Activity — monitoring
ICON_MONITORING: Final[list[Icon]] = _svg_icon(
    "%3Cpolyline points='22 12 18 12 15 21 9 3 6 12 2 12'/%3E"
)

# Database — resources/status
ICON_RESOURCE: Final[list[Icon]] = _svg_icon(
    "%3Cellipse cx='12' cy='5' rx='9' ry='3'/%3E"
    "%3Cpath d='M21 12c0 1.66-4 3-9 3s-9-1.34-9-3'/%3E"
    "%3Cpath d='M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5'/%3E"
)

# Book — reference resources
ICON_REFERENCE: Final[list[Icon]] = _svg_icon(
    "%3Cpath d='M4 19.5A2.5 2.5 0 016.5 17H20'/%3E"
    "%3Cpath d='M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z'/%3E"
)

# Workflow — prompts
ICON_WORKFLOW: Final[list[Icon]] = _svg_icon(
    "%3Cpolyline points='16 18 22 12 16 6'/%3E%3Cpolyline points='8 6 2 12 8 18'/%3E"
)
