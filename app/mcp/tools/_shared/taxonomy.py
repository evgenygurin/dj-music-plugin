"""Taxonomy constants for MCP tools.

Eliminates the magic strings that were scattered across every ``@tool``
decorator — tags, read-only annotations, timeouts. One canonical source,
type-safe enums, no literals in tool modules.

Usage::

    from app.mcp.tools._shared import (
        ANNOTATIONS_READ_ONLY,
        ToolCategory,
        ToolTimeout,
    )

    @tool(
        tags={ToolCategory.CORE},
        annotations=ANNOTATIONS_READ_ONLY,
    )
    async def list_tracks(...) -> PaginatedResponse[TrackBrief]: ...

    @tool(
        tags={ToolCategory.SETS},
        annotations=ANNOTATIONS_WRITE,
        timeout=ToolTimeout.HEAVY,
        task=True,
    )
    async def build_set(...) -> SetSummary: ...
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final


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


# ── Annotation presets (immutable to prevent accidental mutation) ──

#: MCP annotation dict for read-only tools. Use as ``annotations=ANNOTATIONS_READ_ONLY``.
ANNOTATIONS_READ_ONLY: Final[Mapping[str, bool]] = MappingProxyType({"readOnlyHint": True})

#: MCP annotation dict for mutating tools.
ANNOTATIONS_WRITE: Final[Mapping[str, bool]] = MappingProxyType({"readOnlyHint": False})

#: Annotation for read-only tools that reach external systems (YM, Spotify, ...).
ANNOTATIONS_READ_ONLY_OPEN_WORLD: Final[Mapping[str, bool]] = MappingProxyType(
    {"readOnlyHint": True, "openWorldHint": True},
)


class ToolTimeout:
    """Canonical tool execution timeouts (seconds).

    Categories map to operation weight, not to specific tools. Adjust in
    one place rather than searching the codebase for literal ``600.0``.
    """

    #: Interactive operations that should complete within 2 minutes.
    MEDIUM: Final[float] = 120.0

    #: Pipeline operations (build_set, analyze_track) — up to 5 minutes.
    HEAVY: Final[float] = 300.0

    #: Long-running batch jobs (analyze_batch, deliver_set) — up to 10 minutes.
    BATCH: Final[float] = 600.0
