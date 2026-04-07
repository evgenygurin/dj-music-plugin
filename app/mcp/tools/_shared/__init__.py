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

from app.mcp.tools._shared.context import ToolContext
from app.mcp.tools._shared.dispatch import ActionDispatcher, UnknownActionError
from app.mcp.tools._shared.errors import (
    domain_errors_as_tool_error,
    map_domain_errors,
)
from app.mcp.tools._shared.resolvers import (
    ensure_reference,
    resolve_entity,
    resolve_track_id,
)
from app.mcp.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    ANNOTATIONS_WRITE,
    ToolCategory,
    ToolTimeout,
)

__all__ = [
    "ANNOTATIONS_READ_ONLY",
    "ANNOTATIONS_READ_ONLY_OPEN_WORLD",
    "ANNOTATIONS_WRITE",
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
