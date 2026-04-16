"""Split reference resources (Phase 10b).

FastMCP FileSystemProvider auto-discovers @resource-decorated
functions from each submodule.
"""

from app.controllers.resources.reference.camelot import camelot_reference
from app.controllers.resources.reference.key_graph import key_graph_reference
from app.controllers.resources.reference.subgenres import subgenres_reference
from app.controllers.resources.reference.templates import templates_reference

__all__ = [
    "camelot_reference",
    "key_graph_reference",
    "subgenres_reference",
    "templates_reference",
]
