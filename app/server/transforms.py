"""FastMCP v3 transforms.

- ``BM25SearchTransform`` — keeps a fixed set of core tools always visible,
  ranks the rest via BM25 on client queries.
- ``JSONAwarePromptsAsTools`` — exposes prompts as tools for tool-only
  clients; ``get_prompt(arguments=...)`` accepts both native dict and
  JSON-encoded string (Claude Code stdio shim quirk).
- ``JSONAwareResourcesAsTools`` — exposes resources as tools for
  tool-only clients with parsed JSON payloads in ``structuredContent``.
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
from fastmcp.server.transforms.search import BM25SearchTransform

from app.server.json_aware_prompts import JSONAwarePromptsAsTools
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
    "ui_render_studio",
    "ui_control_center",
    # Render pipeline tools — visible by default (like compute/sync verbs).
    "render_beatgrid",
    "render_mixdown",
    "render_diagnose",
    "render_verify",
    "deliver_set",
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

    The two ``JSONAware*`` transforms expose prompts/resources as tools for
    tool-only clients while transparently coercing JSON-string args from
    transports that stringify complex parameters (Claude Code stdio shim).
    ``CodeMode`` is experimental and disabled by default.
    """
    mcp.add_transform(JSONAwarePromptsAsTools(mcp))
    mcp.add_transform(JSONAwareResourcesAsTools(mcp))
    if os.getenv("DJ_MCP_CODE_MODE", "0") == "1" and CodeMode is not None:
        mcp.add_transform(CodeMode(mcp))  # type: ignore[misc,arg-type]
