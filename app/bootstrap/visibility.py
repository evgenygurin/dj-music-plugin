"""Component visibility policy for the MCP server.

Default: all tools visible EXCEPT heavy/dangerous ones (audio, atomic).

Claude Code (and other MCP clients using stdio transport) does NOT
re-fetch the tool list after ``ctx.enable_components`` — so tools
disabled at startup are effectively invisible for the entire session.

Only hide categories that are genuinely dangerous or expensive to call
by accident.  Extended categories (delivery, discovery, curation, sync,
ym) are now always visible so Claude Code can use them without
``unlock_tools``.

Use ``unlock_tools(action="unlock", category="...")`` to enable
audio/atomic per-session when needed.
"""

from __future__ import annotations

from typing import Any

# Only heavy / low-level categories are hidden at startup.
# Extended categories (delivery, discovery, curation, sync, ym)
# are now always visible — see docstring above.
_DISABLED_AT_STARTUP: frozenset[str] = frozenset(
    {
        "audio",
        "atomic",
    }
)


def apply_visibility_policy(mcp: Any) -> None:
    """Apply the stable visibility policy for server components."""
    mcp.disable(tags=_DISABLED_AT_STARTUP)
