"""Private infrastructure for MCP tool implementations.

Naming convention: ``_shared`` (underscore prefix) signals that this is
helper code, not a tool container. FastMCP's ``FileSystemProvider`` only
registers functions decorated with ``@tool``/``@resource``/``@prompt``,
so modules that export utilities (resolvers, facades, decorators, ...)
are safe regardless of location — the underscore is a signal to human
readers.

Exports the stable public API of the shared layer. Tool modules should
import from here, not from individual submodules, so future
restructuring stays non-breaking.
"""

from __future__ import annotations

from app.controllers.tools._shared.context import ToolContext
from app.controllers.tools._shared.dispatch import ActionDispatcher, UnknownActionError
from app.controllers.tools._shared.errors import (
    domain_errors_as_tool_error,
    map_domain_errors,
)
from app.controllers.tools._shared.resolvers import (
    ensure_reference,
    resolve_entity,
    resolve_track_id,
)
from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    ANNOTATIONS_WRITE,
    ANNOTATIONS_WRITE_DESTRUCTIVE,
    ANNOTATIONS_WRITE_DESTRUCTIVE_OPEN,
    ANNOTATIONS_WRITE_IDEMPOTENT,
    ANNOTATIONS_WRITE_OPEN_WORLD,
    ICON_ADMIN,
    ICON_AUDIO,
    ICON_CURATION,
    ICON_DELIVERY,
    ICON_DISCOVERY,
    ICON_MEMORY,
    ICON_PLAYLISTS,
    ICON_REFERENCE,
    ICON_RESOURCE,
    ICON_SEARCH,
    ICON_SETS,
    ICON_SYNC,
    ICON_TRACKS,
    ICON_WORKFLOW,
    ICON_YM,
    RESOURCE_META,
    TOOL_META,
    ToolCategory,
    ToolTimeout,
)

__all__ = [
    "ANNOTATIONS_READ_ONLY",
    "ANNOTATIONS_READ_ONLY_OPEN_WORLD",
    "ANNOTATIONS_WRITE",
    "ANNOTATIONS_WRITE_DESTRUCTIVE",
    "ANNOTATIONS_WRITE_DESTRUCTIVE_OPEN",
    "ANNOTATIONS_WRITE_IDEMPOTENT",
    "ANNOTATIONS_WRITE_OPEN_WORLD",
    "ICON_ADMIN",
    "ICON_AUDIO",
    "ICON_CURATION",
    "ICON_DELIVERY",
    "ICON_DISCOVERY",
    "ICON_MEMORY",
    "ICON_PLAYLISTS",
    "ICON_REFERENCE",
    "ICON_RESOURCE",
    "ICON_SEARCH",
    "ICON_SETS",
    "ICON_SYNC",
    "ICON_TRACKS",
    "ICON_WORKFLOW",
    "ICON_YM",
    "RESOURCE_META",
    "TOOL_META",
    "ActionDispatcher",
    "ToolCategory",
    "ToolContext",
    "ToolTimeout",
    "UnknownActionError",
    "domain_errors_as_tool_error",
    "ensure_reference",
    "map_domain_errors",
    "resolve_entity",
    "resolve_track_id",
]
