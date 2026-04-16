"""FastMCP transform registration helpers."""

from __future__ import annotations

import logging
from typing import Any


def build_pre_constructor_transforms(_logger: logging.Logger | None = None) -> list[Any]:
    """Build transforms passed into the FastMCP constructor.

    BM25SearchTransform was removed because it forces Claude Code to call
    all tools via a ``run_tool`` proxy, which shows "Run Tool" in the UI
    instead of the actual tool name/title.  The native tag-based visibility
    system (``mcp.disable(tags=...)``) is used instead — see
    ``visibility.py``.

    ``build_set`` / ``rebuild_set`` are removed; the declarative flow uses
    ``commit_set_version`` instead — no transforms needed.
    """
    return []


def register_post_constructor_transforms(mcp: Any, logger: logging.Logger | None = None) -> None:
    """Register transforms that require the FastMCP instance."""
    try:
        from fastmcp.server.transforms import PromptsAsTools, ResourcesAsTools

        mcp.add_transform(ResourcesAsTools(mcp))
        mcp.add_transform(PromptsAsTools(mcp))
    except ImportError:
        log = logger or logging.getLogger(__name__)
        log.debug("Post-constructor transforms unavailable")
