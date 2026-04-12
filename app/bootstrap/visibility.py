"""Component visibility policy for the MCP server.

Default: core, sets, admin always visible.
Extended categories (delivery, discovery, curation, sync, ym) start disabled.
Hidden categories (audio, atomic) start disabled.

All disabled categories are unlockable at runtime via
``unlock_tools(action="unlock", category="...")``, which calls
``ctx.fastmcp.enable(tags=...)`` — a server-level operation that triggers
``notifications/tools/list_changed`` so the client re-fetches the tool list.
"""

from __future__ import annotations

from typing import Any

# Categories hidden at startup — unlockable via unlock_tools.
_DISABLED_AT_STARTUP: frozenset[str] = frozenset(
    {
        "delivery",
        "discovery",
        "curation",
        "sync",
        "ym",
        "audio",
        "atomic",
    }
)


def apply_visibility_policy(mcp: Any) -> None:
    """Apply the stable visibility policy for server components."""
    mcp.disable(tags=_DISABLED_AT_STARTUP)
