"""FastMCP transform registration helpers."""

from __future__ import annotations

import logging
from typing import Any


def build_pre_constructor_transforms(logger: logging.Logger | None = None) -> list[Any]:
    """Build transforms passed into the FastMCP constructor."""
    log = logger or logging.getLogger(__name__)
    server_transforms: list[Any] = []

    try:
        from fastmcp.server.transforms.search import BM25SearchTransform

        server_transforms.append(
            BM25SearchTransform(
                max_results=10,
                always_visible=["unlock_tools", "get_library_stats", "run_tool"],
                search_tool_name="search_tools",
                call_tool_name="_bm25_call_tool",
            )
        )
    except ImportError:
        log.warning("BM25SearchTransform not available — install fastmcp[search]")

    return server_transforms


def register_post_constructor_transforms(mcp: Any, logger: logging.Logger | None = None) -> None:
    """Register transforms that require the FastMCP instance."""
    try:
        from fastmcp.server.transforms import PromptsAsTools, ResourcesAsTools

        mcp.add_transform(ResourcesAsTools(mcp))
        mcp.add_transform(PromptsAsTools(mcp))
    except ImportError:
        log = logger or logging.getLogger(__name__)
        log.debug("Post-constructor transforms unavailable")
