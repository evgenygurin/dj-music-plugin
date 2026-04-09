"""Split reference resources (Phase 10b).

FastMCP FileSystemProvider auto-discovers @resource-decorated
functions from each submodule.
"""

from app.controllers.resources.reference.camelot import camelot_reference
from app.controllers.resources.reference.subgenres import subgenres_reference
from app.controllers.resources.reference.templates import templates_reference

__all__ = ["camelot_reference", "subgenres_reference", "templates_reference"]
