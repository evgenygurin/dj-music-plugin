"""Backward-compatibility tool-name shims for v1 → v2 cutover.

Phase 7 of the v2 refactor renames (and in most cases restructures) the
public MCP tool surface. The legacy tree exposed 88 narrow tools
(``build_set``, ``get_track``, ``ym_search`` …). The v2 tree collapses
those into a handful of generic dispatchers:

    * ``entity_list`` / ``entity_get`` / ``entity_create`` /
      ``entity_update`` / ``entity_delete`` / ``entity_aggregate``
    * ``provider_read`` / ``provider_write`` / ``provider_search``
    * ``sequence_optimize`` (replaces ``build_set`` / ``rebuild_set``)
    * ``transition_score_pool`` (replaces ``score_transitions``)
    * ``playlist_sync`` (replaces ``sync_playlist`` / ``push_set_to_ym``)
    * ``unlock_namespace`` (replaces ``unlock_tools``)

Because the v2 dispatchers take different argument shapes (they require
an ``entity_type`` / ``action`` / ``namespace`` discriminator), **no
legacy tool is a pure 1-to-1 rename of a v2 tool**. A pure alias table
therefore cannot provide safe backward compatibility — a shim must also
translate the old call signature into the v2 signature.

Full semantic shims (argument rewriters) are out of scope for Phase 7
Task 3 and tracked as a follow-up. This module intentionally ships an
empty ``TOOL_NAME_ALIASES`` dict plus the ``apply_shims`` scaffolding so
that (a) import-time wiring in ``app/v2/server/app.py`` already exists
and (b) later tasks can add entries without touching the server builder.

Usage (once populated)::

    from fastmcp import FastMCP
    from scripts.compat_shims import apply_shims

    mcp = FastMCP(...)
    # register v2 tools first
    apply_shims(mcp)  # wraps aliases on top
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import FastMCP

# Mapping: legacy tool name -> v2 tool name.
#
# Intentionally empty: every legacy tool maps to a v2 dispatcher with a
# different argument shape, so a name-only alias would route to a tool
# whose inputSchema rejects the legacy arguments. Full semantic shims
# (argument rewriters) are tracked as a follow-up; see module docstring.
TOOL_NAME_ALIASES: dict[str, str] = {}


def apply_shims(mcp: FastMCP) -> None:
    """Register backward-compatibility aliases on ``mcp``.

    For each entry in :data:`TOOL_NAME_ALIASES`, registers a thin wrapper
    tool under the legacy name that forwards to the v2 tool of the same
    underlying signature.

    This is a no-op while ``TOOL_NAME_ALIASES`` is empty. Kept as a
    public hook so callers can wire it unconditionally.
    """
    if not TOOL_NAME_ALIASES:
        return

    # Future: iterate aliases, look up v2 tool via mcp.get_tool(new), wrap
    # as a new @tool under the legacy name that calls through. Must
    # preserve tags / annotations / title from the target tool.
    raise NotImplementedError(
        "apply_shims: argument-rewriting shims not yet implemented; "
        "TOOL_NAME_ALIASES entries require per-tool signature adapters."
    )


__all__ = ["TOOL_NAME_ALIASES", "apply_shims"]
