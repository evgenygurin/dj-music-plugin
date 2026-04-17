"""Namespace-based visibility policy.

Three namespaces are globally disabled at startup:

- ``namespace:crud:destructive`` — entity_update / entity_delete
- ``namespace:provider:write`` — provider_write
- ``namespace:sync`` — playlist_sync

Clients unlock them per-session via the ``unlock_namespace`` tool, which
calls ``ctx.enable_components(tags={"namespace:..."})`` and emits
``notifications/tools/list_changed`` so the tool list refreshes.

The ``unlock_namespace`` tool itself lives in
``app/v2/tools/admin/unlock_namespace.py`` — this module owns the global
policy and re-exports :data:`DISABLED_NAMESPACE_TAGS` and
:data:`KNOWN_NAMESPACES` for it.
"""

from __future__ import annotations

from fastmcp import FastMCP

DISABLED_NAMESPACE_TAGS: frozenset[str] = frozenset(
    {
        "namespace:crud:destructive",
        "namespace:provider:write",
        "namespace:sync",
    }
)

KNOWN_NAMESPACES: frozenset[str] = frozenset(
    {
        "crud:destructive",
        "provider:write",
        "sync",
    }
)


def apply_visibility_policy(mcp: FastMCP) -> None:
    """Disable every tag in :data:`DISABLED_NAMESPACE_TAGS` globally.

    Must be called AFTER all transforms and middleware are registered so the
    composition layer still sees the full tool set; only wire-level listings
    filter them out.
    """
    mcp.disable(tags=set(DISABLED_NAMESPACE_TAGS))
