"""Component visibility policy for the MCP server."""

from __future__ import annotations

from typing import Any


def apply_visibility_policy(mcp: Any) -> None:
    """Apply the stable visibility policy for server components."""
    mcp.disable(tags={"atomic"})
    mcp.disable(names={"_bm25_call_tool"})
