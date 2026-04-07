"""Private infrastructure for MCP tool implementations.

Naming convention: ``_shared`` (underscore prefix) signals that
:class:`~fastmcp.providers.filesystem.FileSystemProvider` must treat this
as a helper package, not a tool container. The provider only registers
functions decorated with ``@tool``/``@resource``/``@prompt``, so modules
that export utilities (resolvers, facades, decorators, ...) are safe
regardless of location — the underscore is a signal to human readers.

Exports the stable public API of the shared layer. Tool modules should
import from here, not from individual submodules, to make future
restructuring non-breaking.
"""

from __future__ import annotations

from app.mcp.tools._shared.context import ToolContext
from app.mcp.tools._shared.dispatch import ActionDispatcher, UnknownActionError
from app.mcp.tools._shared.resolvers import (
    EntityNotFoundError,
    EntityReferenceError,
    ensure_reference,
    resolve_entity,
    resolve_track_id,
)
from app.mcp.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE,
    ToolCategory,
    ToolTimeout,
)

__all__ = [
    "ANNOTATIONS_READ_ONLY",
    "ANNOTATIONS_WRITE",
    "ActionDispatcher",
    "EntityNotFoundError",
    "EntityReferenceError",
    "ToolCategory",
    "ToolContext",
    "ToolTimeout",
    "UnknownActionError",
    "ensure_reference",
    "resolve_entity",
    "resolve_track_id",
]
