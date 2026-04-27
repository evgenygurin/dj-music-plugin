"""FastMCP v3 transforms.

- ``BM25SearchTransform`` — keeps a fixed set of core tools always visible,
  ranks the rest via BM25 on client queries.
- ``PromptsAsTools`` — exposes prompts as tools for tool-only clients.
- ``ResourcesAsTools`` — exposes resources as tools for tool-only clients.
- ``CodeMode`` — optional zero-round-trip pipeline mode, gated by
  ``DJ_MCP_CODE_MODE`` env flag.

Split by lifecycle:

- ``build_pre_constructor_transforms()`` returns transforms that must be
  passed into ``FastMCP(transforms=...)`` BEFORE the server scans tools.
- ``register_post_constructor_transforms(mcp)`` wires transforms that
  need a fully constructed ``mcp`` instance.
"""

from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.transforms import PromptsAsTools
from fastmcp.server.transforms.search import BM25SearchTransform

from app.server.json_aware_resources import JSONAwareResourcesAsTools

try:  # pragma: no cover - optional experimental module
    from fastmcp.experimental.transforms.code_mode import CodeMode
except ImportError:  # pragma: no cover
    CodeMode = None  # type: ignore[assignment,misc]


# Always-visible tools — everything else is BM25-ranked per client query.
# Destructive / provider:write / sync tools are included here now that the
# global visibility gate is off (see app/server/visibility.py rationale).
ALWAYS_VISIBLE_TOOLS: tuple[str, ...] = (
    "entity_list",
    "entity_get",
    "entity_create",
    "entity_update",
    "entity_delete",
    "entity_aggregate",
    "provider_read",
    "provider_search",
    "provider_write",
    "transition_score_pool",
    "sequence_optimize",
    "playlist_sync",
    "unlock_namespace",
    "tool_invoke",
    # Prefab Apps / UI renderers — always visible so Prefab-aware clients
    # discover them without a BM25 query.
    "ui_set_view",
    "ui_transition_score",
    "ui_library_audit",
    "ui_score_pool_matrix",
    "ui_library_dashboard",
    "ui_camelot_wheel",
)


def build_pre_constructor_transforms() -> list[Any]:
    """Transforms that need to be handed to the ``FastMCP(transforms=...)`` arg."""
    return [
        BM25SearchTransform(
            always_visible=list(ALWAYS_VISIBLE_TOOLS),
            max_results=8,
        ),
    ]


def register_post_constructor_transforms(mcp: FastMCP) -> None:
    """Register transforms that need the fully-constructed ``mcp`` instance.

    ``PromptsAsTools`` and ``ResourcesAsTools`` expose prompts/resources as
    tools for tool-only clients. ``CodeMode`` is experimental and disabled
    by default.
    """
    mcp.add_transform(PromptsAsTools(mcp))
    mcp.add_transform(JSONAwareResourcesAsTools(mcp))
    if os.getenv("DJ_MCP_CODE_MODE", "0") == "1" and CodeMode is not None:
        mcp.add_transform(CodeMode(mcp))  # type: ignore[misc,arg-type]
