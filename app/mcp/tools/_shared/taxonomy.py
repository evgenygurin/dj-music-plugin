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
        tags={ToolCategory.CORE.value},
        annotations=ANNOTATIONS_READ_ONLY,
    )
    async def list_tracks(...) -> PaginatedResponse[TrackBrief]: ...

    @tool(
        tags={ToolCategory.SETS.value},
        annotations=ANNOTATIONS_WRITE,
        timeout=ToolTimeout.HEAVY,
        task=True,
    )
    async def build_set(...) -> SetSummary: ...
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Final


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
# FastMCP's ``@tool`` expects ``dict[str, Any]`` for annotations; we
# intentionally use plain dicts (not ``MappingProxyType``) so mypy
# accepts them without casting at every call-site. Do **not** mutate
# these at runtime.

ANNOTATIONS_READ_ONLY: Final[dict[str, Any]] = {"readOnlyHint": True}
ANNOTATIONS_WRITE: Final[dict[str, Any]] = {"readOnlyHint": False}
ANNOTATIONS_READ_ONLY_OPEN_WORLD: Final[dict[str, Any]] = {
    "readOnlyHint": True,
    "openWorldHint": True,
}


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
